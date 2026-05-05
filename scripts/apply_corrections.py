#!/usr/bin/env python3
"""
Apply approved OCR corrections to data/clauses.json and data/markdown/*.md.

Corrections list is hardcoded (one round of human-reviewed fixes). Each entry
specifies the original token, the replacement, and the contract_id(s) where it
should apply — to prevent collateral edits in unrelated contracts.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUSES = ROOT / "data" / "clauses.json"
MD_DIR = ROOT / "data" / "markdown"

# Reviewed 2026-05-05 — high-confidence single-token OCR misreads only.
CORRECTIONS = [
    # original, replacement, scope (list of contract_ids; None = all)
    ("eamed",       "earned",       ["dc37-l1087-locksmiths-consent-determination-2021-2026",
                                      "dc37-l983-high-pressure-plant-tenders-consent-determination-2022-2027",
                                      "ibt-l237-maintenance-workers-consent-determination-2022-2027"]),
    ("eaming",      "earning",      ["local-14-15-gasoline-roller-engineers-wage-indenture-2021-2026"]),
    ("carning",     "earning",      ["ibt-l237-cement-masons-consent-determination-2020-2025",
                                      "ibt-l237-maintenance-workers-consent-determination-2022-2027"]),
    ("Amicle",      "Article",      ["usa-executed-contract-2022-2028"]),
    ("Emplovee",    "Employee",     ["dc37-moa-2021-2026"]),
    ("Govemmental", "Governmental", ["usa-executed-contract-2022-2028"]),
    ("Intems",      "Interns",      ["cir-executed-contract-2021-2027"]),
    ("conceming",   "concerning",   ["cca-unit-agreement-2022-2028"]),
    ("govemment",   "government",   ["ale-executed-contract-2021-2027"]),
    ("jointlv",     "jointly",      ["usa-executed-contract-2022-2028"]),
    ("salarv",      "salary",       ["osa-public-advocate-executed-contract-2022-2026"]),
    ("vear",        "year",         ["l3-electricians-consent-determination-20232028"]),
]


def apply_to_clauses():
    clauses = json.loads(CLAUSES.read_text())
    total = 0
    for clause in clauses:
        for original, replacement, scope in CORRECTIONS:
            if scope and clause.get("contract_id") not in scope:
                continue
            text = clause.get("text") or ""
            pattern = r"\b" + re.escape(original) + r"\b"
            new_text, n = re.subn(pattern, replacement, text)
            if n:
                clause["text"] = new_text
                total += n
                print(f"  {clause['contract_id']:60} {original!r:14} → {replacement!r}  ×{n}")
    CLAUSES.write_text(json.dumps(clauses, indent=1, ensure_ascii=False) + "\n")
    return total


def apply_to_markdown():
    total = 0
    for original, replacement, scope in CORRECTIONS:
        targets = [MD_DIR / f"{c}.md" for c in (scope or [])]
        for path in targets:
            if not path.exists():
                continue
            text = path.read_text()
            pattern = r"\b" + re.escape(original) + r"\b"
            new_text, n = re.subn(pattern, replacement, text)
            if n:
                path.write_text(new_text)
                total += n
                print(f"  {path.name:60} {original!r:14} → {replacement!r}  ×{n}")
    return total


def maybe_load_extra_corrections():
    """Optionally load additional corrections from data/ocr-corrections-batch2.json."""
    extra_path = ROOT / "data" / "ocr-corrections-batch2.json"
    if not extra_path.exists():
        return
    items = json.loads(extra_path.read_text())
    for item in items:
        CORRECTIONS.append((item["original"], item["replacement"], item["contracts"]))
    print(f"(loaded {len(items)} extra corrections from {extra_path.name})")


if __name__ == "__main__":
    import sys
    if "--batch2" in sys.argv:
        # Replace hardcoded list with batch 2 only
        CORRECTIONS.clear()
        maybe_load_extra_corrections()
    print("=== clauses.json ===")
    n1 = apply_to_clauses()
    print(f"\n=== markdown/ ===")
    n2 = apply_to_markdown()
    print(f"\nTotal: {n1} replacements in clauses.json, {n2} in markdown.")
