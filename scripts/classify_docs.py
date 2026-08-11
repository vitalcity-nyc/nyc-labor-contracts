"""Classify each contract by document type and write it into contracts.json.

Most documents OLR publishes are NOT standalone contracts. They are short
amendments that change a handful of economic terms and leave an underlying
agreement — which OLR generally does not publish — in force. Presenting them
in the same visual class as a 400,000-character full agreement misleads the
reader about what they are looking at.

This script assigns every contract:

  doc_type            one of full-agreement | moa | consent-determination |
                      unit-agreement
  amends_predecessor  True when the document explicitly says the prior
                      agreement's terms continue except as modified here
  amends_evidence     the verbatim sentence fragment that justified the flag

Classification uses document TEXT first and the label only as a tiebreak, so a
mislabeled file still lands in the right bucket. Every flag is evidence-backed
and auditable; nothing is inferred from length alone.
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# A document that continues a predecessor agreement. These phrasings are the
# standard OLR/union boilerplate for "this is an amendment, not a new contract".
AMENDS_RE = re.compile(
    r"("
    r"terms?\s+of\s+the\s+predecessor[^.]{0,120}?(?:continued|remain)"
    r"|predecessor\s+(?:separate\s+)?unit\s+agreement[^.]{0,120}?continued"
    r"|all\s+other\s+terms[^.]{0,120}?(?:remain|continue)"
    r"|shall\s+be\s+continued\s+except\s+as\s+modified"
    r"|remain\s+in\s+full\s+force\s+and\s+effect\s+except"
    r"|except\s+as\s+(?:modified|amended|changed)\s+(?:herein|by\s+this)"
    r")",
    re.I,
)

# Comptroller wage orders for skilled trades under NY Labor Law 220. These are
# not bargained contracts at all — they are determinations that fix prevailing
# rates, usually carrying a full Appendix A of time-and-leave benefits.
CONSENT_RE = re.compile(
    r"(consent\s+determination|wage\s+indenture"
    r"|comptroller\s+of\s+the\s+city\s+of\s+new\s+york"
    r"|labor\s+law\s+section\s+220|section\s+220\.8)",
    re.I,
)

# Uniformed unit-bargaining letters executed under the Uniformed Officers
# Coalition Economic Agreement. Economic terms live in the parent UOCEA.
UNIT_RE = re.compile(
    r"(unit\s+bargaining|uniform(?:ed)?\s+officers?\s+coalition"
    r"|\bUOCEA\b|\bVOCEA\b)",
    re.I,
)

# Structural markers of a standalone, self-contained agreement. Segmentation
# lifts "ARTICLE X" lines out of the body into each clause's heading, so count
# articles across headings AND body or every real agreement scores zero.
ARTICLE_RE = re.compile(r"^\s*ARTICLE\s+(?:[IVXLC]+|\d+)\b", re.I | re.M)
ARTICLE_HEAD_RE = re.compile(r"^\s*Article\s+(?:[IVXLC]+|\d+)\b", re.I)

LABELS = {
    "full-agreement": "Full agreement",
    "moa": "Amendment (MOA)",
    "consent-determination": "Consent determination",
    "unit-agreement": "Unit agreement",
}


def classify(contract, text, headings):
    """Return (doc_type, amends_predecessor, evidence)."""
    m = AMENDS_RE.search(text)
    amends = bool(m)
    evidence = " ".join(m.group(0).split())[:180] if m else None

    n_articles = len(ARTICLE_RE.findall(text)) + sum(
        1 for h in headings if ARTICLE_HEAD_RE.match(h or ""))

    # Consent determinations and wage indentures are their own instrument.
    if CONSENT_RE.search(text[:6000]) or "consent determination" in contract["label"].lower() \
            or "wage indenture" in contract["label"].lower():
        return "consent-determination", amends, evidence

    # Uniformed unit-bargaining letters under the coalition agreement.
    if UNIT_RE.search(text[:6000]):
        return "unit-agreement", amends, evidence

    # A document with a real article structure and substantial length is a
    # standalone agreement even if it also contains amending language.
    if n_articles >= 8 and len(text) > 40000:
        return "full-agreement", amends, evidence

    # Everything else that continues a predecessor is an amendment.
    if amends:
        return "moa", amends, evidence

    # No amending language and no article structure: still an MOA in practice
    # (short economic memoranda), but flag long ones as full agreements.
    if len(text) > 40000 and n_articles >= 4:
        return "full-agreement", amends, evidence
    return "moa", amends, evidence


def main():
    contracts = json.loads((DATA / "contracts.json").read_text())
    clauses = json.loads((DATA / "clauses.json").read_text())
    by_contract = defaultdict(list)
    for cl in clauses:
        by_contract[cl["contract_id"]].append(cl)

    counts = Counter()
    n_amend = 0
    for c in contracts:
        items = by_contract.get(c["id"], [])
        text = "\n".join(x["text"] for x in items)
        headings = [x.get("heading") or "" for x in items]
        if not text:
            print(f"[warn] no text for {c['id']}", file=sys.stderr)
        doc_type, amends, evidence = classify(c, text, headings)
        c["doc_type"] = doc_type
        c["amends_predecessor"] = amends
        c["amends_evidence"] = evidence
        c["chars"] = len(text)
        counts[doc_type] += 1
        n_amend += bool(amends)

    (DATA / "contracts.json").write_text(json.dumps(contracts, indent=1))

    print(f"Classified {len(contracts)} documents:")
    for k, n in counts.most_common():
        ids = [c for c in contracts if c["doc_type"] == k]
        med = sorted(x["chars"] for x in ids)[len(ids) // 2]
        print(f"  {n:>3}  {LABELS[k]:<24} median {med:>8,} chars")
    print(f"\n{n_amend} documents explicitly continue a predecessor agreement.")


if __name__ == "__main__":
    main()
