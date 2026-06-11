#!/usr/bin/env python3
"""Make data/text/ the single corrected canonical text layer.

Two repairs, in order:
  1. Vision merge — for contracts re-OCR'd via Google Cloud Vision
     (data/text-vision/), overwrite the data/text/ sidecars with the Vision
     text, which is far cleaner than the original macOS OCR still sitting
     there.
  2. Corrections — apply every human-reviewed OCR correction batch (the
     hardcoded round in apply_corrections.py plus batches 2-5) directly to
     data/text/*.txt and *.pages.json, scoped per contract.

After this, everything downstream (segment -> clauses.json -> site search,
export_markdown, export_text_only) can rebuild from data/text/ without
losing any past accuracy work.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TXT = DATA / "text"
VISION = DATA / "text-vision"

sys.path.insert(0, str(ROOT / "scripts"))
from apply_corrections import CORRECTIONS as HARDCODED  # noqa: E402


def merge_vision():
    n = 0
    for vf in sorted(VISION.glob("*.pages.json")):
        doc = json.loads(vf.read_text())
        cid = doc["contract_id"]
        vpages = doc["pages"]
        new_meta = []
        parts = []
        for p in vpages:
            text = (p.get("text") or "").strip()
            new_meta.append({
                "page": p["page"],
                "words": len(text.split()),
                "tables": 0,
                "ocr": True,           # still OCR, just a better engine
                "engine": "google-cloud-vision",
                "text": text,
            })
            parts.append(text)
        (TXT / f"{cid}.pages.json").write_text(json.dumps(new_meta, indent=1, ensure_ascii=False))
        (TXT / f"{cid}.txt").write_text("\n\f\n".join(parts))
        n += 1
        print(f"  vision -> text/: {cid} ({len(vpages)} pages)")
    return n


def load_all_corrections():
    """[(original, replacement, scope-or-None), ...] from every batch."""
    corr = list(HARDCODED)
    for b in (2, 3, 4, 5):
        f = DATA / f"ocr-corrections-batch{b}.json"
        if not f.exists():
            continue
        for item in json.loads(f.read_text()):
            corr.append((item["original"], item["replacement"], item["contracts"] or None))
    # one-off from the earliest fix (commit 750d661), kept for completeness
    corr.append(("Pavments", "Payments", ["cir-executed-contract-2021-2027"]))
    return corr


def apply_corrections():
    corr = load_all_corrections()
    print(f"  loaded {len(corr)} correction rules")
    by_contract = {}
    for orig, repl, scope in corr:
        if scope:
            for cid in scope:
                by_contract.setdefault(cid, []).append((orig, repl))
        else:
            by_contract.setdefault(None, []).append((orig, repl))
    global_rules = by_contract.pop(None, [])

    total = 0
    for tf in sorted(TXT.glob("*.txt")):
        cid = tf.stem
        rules = global_rules + by_contract.get(cid, [])
        if not rules:
            continue
        text = tf.read_text()
        n_file = 0
        for orig, repl in rules:
            pattern = r"\b" + re.escape(orig) + r"\b"
            text, n = re.subn(pattern, repl, text)
            n_file += n
        if n_file:
            tf.write_text(text)
            # mirror into pages.json
            pj = TXT / f"{cid}.pages.json"
            if pj.exists():
                pages = json.loads(pj.read_text())
                for p in pages:
                    t = p.get("text") or ""
                    for orig, repl in rules:
                        t = re.sub(r"\b" + re.escape(orig) + r"\b", repl, t)
                    p["text"] = t
                pj.write_text(json.dumps(pages, indent=1, ensure_ascii=False))
            total += n_file
            print(f"  {cid}: {n_file} replacements")
    return total


if __name__ == "__main__":
    print("=== 1. Vision merge ===")
    nv = merge_vision()
    print(f"\n=== 2. Correction batches -> sidecars ===")
    nc = apply_corrections()
    print(f"\nDone: {nv} contracts re-sourced from Vision; {nc} corrections applied to canonical text.")
