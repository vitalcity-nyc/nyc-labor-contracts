"""Split each contract's text into clauses (article/section).

Inputs : data/text/<id>.txt + data/text/<id>.pages.json + data/contracts.json
Output : data/clauses.json — list of {id, contract_id, contract_label, article,
         article_label, section, section_label, heading, text, page, ocr}
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TXT_DIR = DATA / "text"

# Heading regex covers: ARTICLE I, Article 1, Section 1., Section 1.2, "1.", "1.1.",
# and named clauses (RECOGNITION, GRIEVANCE PROCEDURE, etc.).
ARTICLE_RE = re.compile(
    r"^(?:ARTICLE|Article)\s+(?P<num>[IVXLC]+|\d+)(?:[\.:\-\s]+(?P<title>.+?))?\s*$"
)
SECTION_RE = re.compile(
    r"^(?:SECTION|Section|Sec\.)\s+(?P<num>\d+(?:\.\d+)?)(?:[\.:\-\s]+(?P<title>.+?))?\s*$"
)
NUMBERED_RE = re.compile(r"^(?P<num>\d+)\.\s+(?P<title>[A-Z][A-Z &/'\-]{4,}?)\s*$")
ALL_CAPS_HEAD_RE = re.compile(r"^(?P<title>[A-Z][A-Z 0-9&'/\-]{4,}?)\s*$")


def _page_for_offset(offsets, off):
    """Given list of (start_offset, page_no) sorted by start, return page for off."""
    lo, hi = 0, len(offsets) - 1
    page = 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if offsets[mid][0] <= off:
            page = offsets[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return page


def segment_contract(contract):
    cid = contract["id"]
    txt_path = TXT_DIR / f"{cid}.txt"
    pages_path = TXT_DIR / f"{cid}.pages.json"
    if not txt_path.exists():
        return []
    full = txt_path.read_text()
    # Build page offset table from form-feeds we wrote between pages.
    offsets = [(0, 1)]
    cur = 0
    page = 1
    for line in full.split("\n"):
        if "\f" in line:
            page += 1
            offsets.append((cur, page))
        cur += len(line) + 1
    pages_meta = []
    if pages_path.exists():
        try:
            pages_meta = json.loads(pages_path.read_text())
        except Exception:
            pages_meta = []
    ocr_pages = {p["page"] for p in pages_meta if p.get("ocr")}

    lines = full.splitlines()
    # Walk lines, identify headings, collect bodies.
    boundaries = []  # (line_idx, level, num, title)
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        m = ARTICLE_RE.match(line)
        if m:
            boundaries.append((i, "article", m.group("num"), (m.group("title") or "").strip()))
            continue
        m = SECTION_RE.match(line)
        if m:
            boundaries.append((i, "section", m.group("num"), (m.group("title") or "").strip()))
            continue
        m = NUMBERED_RE.match(line)
        if m and len(line) <= 80:
            boundaries.append((i, "section", m.group("num"), m.group("title").strip()))
            continue
        m = ALL_CAPS_HEAD_RE.match(line)
        if m and 5 <= len(line) <= 60:
            boundaries.append((i, "section", "", m.group("title").strip()))
            continue

    clauses = []
    if not boundaries:
        # Whole-doc as a single clause (rare, e.g. very short MOAs)
        clauses.append({
            "id": f"{cid}__whole",
            "contract_id": cid,
            "article": None,
            "article_label": None,
            "section": None,
            "section_label": None,
            "heading": contract["label"],
            "text": full.strip(),
            "page": 1,
            "ocr": bool(ocr_pages),
        })
        return clauses

    cur_article = None
    cur_article_label = None
    for j, (li, level, num, title) in enumerate(boundaries):
        end_li = boundaries[j + 1][0] if j + 1 < len(boundaries) else len(lines)
        body = "\n".join(lines[li + 1:end_li]).strip()
        if level == "article":
            cur_article = num
            cur_article_label = title
            heading = f"Article {num}" + (f" — {title}" if title else "")
            section = None
            section_label = None
        else:
            section = num if num else None
            section_label = title
            if section:
                heading = f"Section {section}" + (f" — {title}" if title else "")
            else:
                heading = title

        # Compute char offset of this line for page lookup
        char_off = sum(len(lines[k]) + 1 for k in range(li))
        page = _page_for_offset(offsets, char_off)

        clauses.append({
            "id": f"{cid}__{j}",
            "contract_id": cid,
            "article": cur_article,
            "article_label": cur_article_label,
            "section": section,
            "section_label": section_label,
            "heading": heading,
            "text": body,
            "page": page,
            "ocr": page in ocr_pages,
        })
    # Drop empty clauses
    clauses = [c for c in clauses if c["text"]]
    return clauses


def main():
    contracts = json.loads((DATA / "contracts.json").read_text())
    out = []
    for c in contracts:
        cl = segment_contract(c)
        if cl:
            print(f"{c['id']}: {len(cl)} clauses", file=sys.stderr)
            out.extend(cl)
    (DATA / "clauses.json").write_text(json.dumps(out, indent=1))
    print(f"\nTotal: {len(out)} clauses across {len(contracts)} contracts", file=sys.stderr)


if __name__ == "__main__":
    main()
