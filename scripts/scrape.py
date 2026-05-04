"""Download every contract PDF in data/contracts.json to data/pdfs/<id>.pdf."""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PDF_DIR = DATA / "pdfs"
PDF_DIR.mkdir(exist_ok=True, parents=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; nyc-labor-contracts/0.1)"}


def main():
    contracts = json.loads((DATA / "contracts.json").read_text())
    n_ok = n_skip = n_fail = 0
    for c in contracts:
        out = PDF_DIR / f"{c['id']}.pdf"
        if out.exists() and out.stat().st_size > 1000:
            n_skip += 1
            continue
        try:
            r = requests.get(c["url"], headers=UA, timeout=60)
            r.raise_for_status()
            if not r.content[:4] == b"%PDF":
                print(f"[fail] {c['id']}: not a PDF", file=sys.stderr)
                n_fail += 1
                continue
            out.write_bytes(r.content)
            print(f"[ok] {c['id']}: {len(r.content)//1024} KB")
            n_ok += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"[fail] {c['id']}: {e}", file=sys.stderr)
            n_fail += 1
    print(f"\nfetched={n_ok} cached={n_skip} failed={n_fail}", file=sys.stderr)


if __name__ == "__main__":
    main()
