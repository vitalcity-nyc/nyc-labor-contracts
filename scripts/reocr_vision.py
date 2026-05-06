#!/usr/bin/env python3
"""
Re-OCR the worst-quality contracts using Google Cloud Vision (DOCUMENT_TEXT_DETECTION).

Targets every contract flagged ocr_quality='poor' in contracts.json. For each,
renders each page of the source PDF to PNG with PyMuPDF, sends to Vision, and
writes the result to data/text-vision/<contract_id>.pages.json so we can diff
against the existing macOS Vision OCR before deciding what to merge.

Setup required (one-time):
  1. Google Cloud project with Vision API enabled
  2. Service account JSON key downloaded
  3. export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
  4. pip3 install google-cloud-vision (already done in this environment)
"""
import json
import os
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "pdfs"
OUT_DIR = ROOT / "data" / "text-vision"
CONTRACTS = ROOT / "data" / "contracts.json"


def get_vision_client():
    try:
        from google.cloud import vision
    except ImportError:
        sys.exit("Run: pip3 install google-cloud-vision --user")
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sys.exit("Set GOOGLE_APPLICATION_CREDENTIALS to your service-account JSON path.")
    return vision.ImageAnnotatorClient()


def reocr_pdf(client, pdf_path, contract_id):
    from google.cloud import vision
    doc = fitz.open(str(pdf_path))
    pages_out = []
    for i, page in enumerate(doc, start=1):
        # Render at 200 DPI — good balance of quality/cost (Vision charges per
        # request, not per pixel, so higher DPI is free)
        pix = page.get_pixmap(dpi=200)
        png_bytes = pix.tobytes("png")
        image = vision.Image(content=png_bytes)
        # DOCUMENT_TEXT_DETECTION is tuned for dense text like contracts
        feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
        request = vision.AnnotateImageRequest(image=image, features=[feature])
        response = client.annotate_image(request)
        if response.error.message:
            print(f"  page {i}: ERROR {response.error.message}")
            pages_out.append({"page": i, "error": response.error.message})
            continue
        text = response.full_text_annotation.text or ""
        confidence = (response.full_text_annotation.pages[0].confidence
                      if response.full_text_annotation.pages else None)
        pages_out.append({
            "page": i,
            "text": text,
            "confidence": confidence,
            "char_count": len(text),
        })
        sys.stdout.write(f".")
        sys.stdout.flush()
    sys.stdout.write("\n")
    return pages_out


def main():
    OUT_DIR.mkdir(exist_ok=True)
    contracts = json.loads(CONTRACTS.read_text())
    targets = [c for c in contracts if c.get("ocr_quality") == "poor"]
    print(f"Re-OCR'ing {len(targets)} 'poor' contracts via Google Cloud Vision")

    client = get_vision_client()
    for contract in targets:
        cid = contract["id"]
        pdf = PDF_DIR / f"{cid}.pdf"
        out = OUT_DIR / f"{cid}.pages.json"
        if not pdf.exists():
            print(f"SKIP {cid}: PDF not found at {pdf}")
            continue
        if out.exists():
            print(f"SKIP {cid}: already re-OCR'd at {out.name}")
            continue
        print(f"\n→ {cid} ({pdf.stat().st_size // 1024} KB)")
        pages = reocr_pdf(client, pdf, cid)
        out.write_text(json.dumps({
            "contract_id": cid,
            "engine": "google-cloud-vision",
            "pages": pages,
        }, indent=2, ensure_ascii=False))
        total_chars = sum(p.get("char_count", 0) for p in pages)
        print(f"  wrote {len(pages)} pages, {total_chars:,} chars → {out.name}")


if __name__ == "__main__":
    main()
