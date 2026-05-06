#!/usr/bin/env python3
"""
Merge Google Cloud Vision OCR results into clauses.json and markdown/.

For each contract flagged ocr_quality='poor', drop its existing clauses and
replace with one clean clause per PDF page, sourced from the Vision OCR pass
(data/text-vision/<contract_id>.pages.json). Then regenerate the markdown
file for that contract.

The existing clauses for these contracts had heading detection driven by
heavily-garbled OCR, producing fragmented topic tags that aren't trustworthy
anyway. Page-level granularity is plenty for a search-and-quote use case.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUSES = ROOT / "data" / "clauses.json"
CONTRACTS = ROOT / "data" / "contracts.json"
VISION_DIR = ROOT / "data" / "text-vision"
MD_DIR = ROOT / "data" / "markdown"


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def regenerate_markdown(contract, vision_pages):
    cid = contract["id"]
    label = contract["label"]
    expanded = contract.get("expanded_label") or label
    term = f"{contract.get('term_start','?')}–{contract.get('term_end','?')}"
    pdf_url = contract.get("url", "")
    sector = contract.get("sector", "other")
    n_pages = len(vision_pages)
    lines = [
        "---",
        f"contract_id: {cid}",
        f'label: "{label}"',
        f'expanded_label: "{expanded}"',
        f"term_start: {contract.get('term_start','')}",
        f"term_end: {contract.get('term_end','')}",
        f'source_pdf: "{pdf_url}"',
        f"pages: {n_pages}",
        f"ocr_pages: {n_pages}",
        f"ocr_engine: google-cloud-vision",
        f"clauses: {n_pages}",
        f'sector: "{sector}"',
        "---",
        "",
        f"# {expanded}",
        "",
        f"**Term:** {term}  ",
        f"**Source PDF:** [{pdf_url}]({pdf_url})  ",
        f"**Pages:** {n_pages} (re-OCR'd via Google Cloud Vision)",
        "",
        "> This contract was originally OCR'd via macOS Vision and contained heavy "
        "transcription errors. It was re-processed with Google Cloud Vision's "
        "DOCUMENT_TEXT_DETECTION on " + __import__("datetime").date.today().isoformat() +
        ". The text below is the re-OCR'd output. Verify quotations against the "
        "source PDF before publishing.",
        "",
        "---",
        "",
    ]
    for p in vision_pages:
        page_num = p["page"]
        text = (p.get("text") or "").strip()
        if not text:
            continue
        anchor = f"page-{page_num}"
        lines += [
            f'<a id="{anchor}"></a>',
            f"### Page {page_num}",
            "_OCR via Google Cloud Vision_",
            "",
            text,
            "",
        ]
    return "\n".join(lines) + "\n"


def main():
    contracts = json.loads(CONTRACTS.read_text())
    clauses = json.loads(CLAUSES.read_text())
    by_id = {c["id"]: c for c in contracts}

    poor_ids = [c["id"] for c in contracts if c.get("ocr_quality") == "poor"]
    print(f"Merging Vision OCR for {len(poor_ids)} contracts:")
    for cid in poor_ids:
        print(f"  - {cid}")

    # Drop existing clauses for these contracts
    new_clauses = [c for c in clauses if c["contract_id"] not in poor_ids]
    dropped = len(clauses) - len(new_clauses)
    print(f"\nDropped {dropped} existing OCR'd clauses for poor contracts")

    # Insert one clause per Vision-OCR'd page
    inserted = 0
    md_written = 0
    for cid in poor_ids:
        vfile = VISION_DIR / f"{cid}.pages.json"
        if not vfile.exists():
            print(f"  SKIP {cid}: no vision file")
            continue
        v = json.loads(vfile.read_text())
        pages = v["pages"]
        for p in pages:
            text = (p.get("text") or "").strip()
            if not text:
                continue
            new_clauses.append({
                "id": f"{cid}__p{p['page']}",
                "contract_id": cid,
                "article": None,
                "article_label": None,
                "section": None,
                "section_label": f"Page {p['page']}",
                "heading": f"Page {p['page']}",
                "text": text,
                "page": p["page"],
                "ocr": True,
                "ocr_engine": "google-cloud-vision",
                "topics": [],
            })
            inserted += 1
        # Regenerate markdown
        contract = by_id.get(cid)
        if contract:
            md = regenerate_markdown(contract, pages)
            (MD_DIR / f"{cid}.md").write_text(md)
            md_written += 1

    # Sort clauses by contract_id then page (stable ordering)
    new_clauses.sort(key=lambda c: (c["contract_id"], c.get("page") or 0, c["id"]))

    CLAUSES.write_text(json.dumps(new_clauses, indent=1, ensure_ascii=False) + "\n")
    print(f"\nInserted {inserted} new page-level clauses")
    print(f"Regenerated {md_written} markdown files")
    print(f"clauses.json now has {len(new_clauses)} clauses (was {len(clauses)})")


if __name__ == "__main__":
    main()
