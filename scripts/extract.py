"""Quality-aware text extraction from contract PDFs.

For each PDF in data/pdfs:
  - extract page-by-page with pdfplumber
  - preserve tables as pipe-delimited markdown (so columns survive in the search corpus)
  - detect and split multi-column pages so reading order is left-column-first
  - score each page; if a page is empty / sparse / below threshold, render at 300dpi
    and OCR via macOS Vision (ocrmac)
  - write data/text/<id>.txt with FORM-FEED page separators ("\f") and a sidecar
    data/text/<id>.pages.json with per-page metadata (text, words, ocr, tables)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PDF_DIR = DATA / "pdfs"
TXT_DIR = DATA / "text"
TXT_DIR.mkdir(exist_ok=True, parents=True)

MIN_WORDS_PER_PAGE = 20  # below this, treat the page as suspect → try OCR
ALPHA_RATIO_MIN = 0.55   # text-layer text should be mostly letters/spaces/punct


def _ocr_page(pdf_path: Path, page_index: int) -> str:
    """Render one page at 300dpi and run macOS Vision OCR. Returns recovered text."""
    try:
        import pypdfium2 as pdfium
        from ocrmac import ocrmac
    except Exception as e:
        print(f"  ocr unavailable: {e}", file=sys.stderr)
        return ""
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[page_index]
    pil = page.render(scale=300 / 72).to_pil()
    tmp = pdf_path.parent.parent / "text" / f".ocr-{pdf_path.stem}-{page_index}.png"
    pil.save(tmp, "PNG")
    try:
        annotations = ocrmac.OCR(str(tmp), recognition_level="accurate").recognize()
    except Exception as e:
        print(f"  ocr error p{page_index+1}: {e}", file=sys.stderr)
        annotations = []
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    # annotations: list of (text, confidence, bbox) sorted by Vision; keep top-down
    lines = []
    for item in annotations:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            txt = item[0]
            if isinstance(txt, str) and txt.strip():
                lines.append(txt.rstrip())
    return "\n".join(lines)


def _table_to_markdown(table) -> str:
    if not table or not table[0]:
        return ""
    rows = []
    for row in table:
        cells = ["" if c is None else " ".join(str(c).split()) for c in row]
        rows.append("| " + " | ".join(cells) + " |")
    if len(rows) >= 1:
        ncols = len(table[0])
        sep = "| " + " | ".join(["---"] * ncols) + " |"
        rows.insert(1, sep)
    return "\n".join(rows)


def _alpha_ratio(s: str) -> float:
    if not s:
        return 0.0
    keep = sum(1 for ch in s if ch.isalpha() or ch.isspace() or ch in ".,;:!?-()/&%$'\"")
    return keep / max(len(s), 1)


def _detect_columns(page) -> int:
    """Return 1 if single-column, 2 if likely two-column. Heuristic: look at the
    distribution of character x-midpoints; a bimodal distribution → two columns."""
    chars = page.chars
    if len(chars) < 200:
        return 1
    width = page.width or 612
    mid = width / 2
    left = sum(1 for c in chars if (c["x0"] + c["x1"]) / 2 < mid)
    right = len(chars) - left
    # Two-column pages have roughly balanced halves AND a clear gutter (few chars near mid)
    bal = min(left, right) / max(left, right)
    near_mid = sum(1 for c in chars if abs(((c["x0"] + c["x1"]) / 2) - mid) < width * 0.04)
    gutter = near_mid / len(chars)
    if bal > 0.4 and gutter < 0.05:
        return 2
    return 1


def _extract_page_text(page, page_no: int):
    """Extract text from a single page, preserving tables and column order.
    Returns (text, word_count, table_count, ocr_used:bool)."""
    parts = []
    table_count = 0

    # Try tables first; remember their bounding boxes to mask them out of the text pass.
    table_bboxes = []
    try:
        for tbl_obj in page.find_tables():
            data = tbl_obj.extract()
            md = _table_to_markdown(data)
            if md:
                parts.append("\n" + md + "\n")
                table_count += 1
                table_bboxes.append(tbl_obj.bbox)
    except Exception:
        pass

    # Crop to a non-table region (only one large mask if any tables)
    text_page = page
    if table_bboxes:
        try:
            # Build a list of "non-table" stripes by exclusion
            text_page = page.filter(lambda obj: not any(
                obj["x0"] >= bbox[0] - 1 and obj["x1"] <= bbox[2] + 1 and
                obj["top"] >= bbox[1] - 1 and obj["bottom"] <= bbox[3] + 1
                for bbox in table_bboxes
            ))
        except Exception:
            text_page = page

    cols = _detect_columns(page)
    page_text = ""
    try:
        if cols == 2:
            half = (page.width or 612) / 2
            left_crop = text_page.crop((0, 0, half, page.height or 792), strict=False)
            right_crop = text_page.crop((half, 0, page.width or 612, page.height or 792), strict=False)
            l = left_crop.extract_text(x_tolerance=2, y_tolerance=2, layout=False) or ""
            r = right_crop.extract_text(x_tolerance=2, y_tolerance=2, layout=False) or ""
            page_text = (l + "\n" + r).strip()
        else:
            page_text = text_page.extract_text(x_tolerance=2, y_tolerance=2, layout=False) or ""
    except Exception:
        page_text = ""

    if page_text.strip():
        parts.append(page_text)

    text = "\n".join(parts).strip()
    words = len(re.findall(r"\b\w+\b", text))
    return text, words, table_count, False


def extract_pdf(pdf_path: Path):
    """Return list of page dicts and the joined full text."""
    pages_meta = []
    full_text_parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                text, words, ntables, _ = _extract_page_text(page, i + 1)
            except Exception as e:
                print(f"  p{i+1} extract error: {e}", file=sys.stderr)
                text, words, ntables = "", 0, 0
            ocr_used = False
            quality_low = (words < MIN_WORDS_PER_PAGE) or (text and _alpha_ratio(text) < ALPHA_RATIO_MIN)
            if quality_low:
                # Try OCR on this page
                ocr_text = _ocr_page(pdf_path, i)
                ocr_words = len(re.findall(r"\b\w+\b", ocr_text))
                if ocr_words > words:
                    text = ocr_text
                    words = ocr_words
                    ocr_used = True
            pages_meta.append({
                "page": i + 1,
                "words": words,
                "tables": ntables,
                "ocr": ocr_used,
                "text": text,
            })
            full_text_parts.append(text)
    return pages_meta, "\n\f\n".join(full_text_parts)


def main(only_id: str | None = None):
    contracts = json.loads((DATA / "contracts.json").read_text())
    n_done = n_skip = n_fail = 0
    for c in contracts:
        if only_id and c["id"] != only_id:
            continue
        pdf_path = PDF_DIR / f"{c['id']}.pdf"
        if not pdf_path.exists():
            continue
        txt_path = TXT_DIR / f"{c['id']}.txt"
        meta_path = TXT_DIR / f"{c['id']}.pages.json"
        if txt_path.exists() and meta_path.exists() and txt_path.stat().st_size > 100:
            n_skip += 1
            continue
        print(f"[extract] {c['id']} ...", file=sys.stderr)
        try:
            pages, full = extract_pdf(pdf_path)
            txt_path.write_text(full)
            meta_path.write_text(json.dumps(pages, indent=1))
            ocr_pages = sum(1 for p in pages if p["ocr"])
            tbls = sum(p["tables"] for p in pages)
            print(f"  pages={len(pages)} ocr={ocr_pages} tables={tbls} chars={len(full)}", file=sys.stderr)
            n_done += 1
        except Exception as e:
            print(f"[fail] {c['id']}: {e}", file=sys.stderr)
            n_fail += 1
    print(f"\nextracted={n_done} cached={n_skip} failed={n_fail}", file=sys.stderr)


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    main(only)
