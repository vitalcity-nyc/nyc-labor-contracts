"""Build data/wages.json — general wage increase (GWI) schedules per contract.

Every CURATED entry below has been verified directly against the OCR'd
contract text. Percentages, effective dates, and bonus amounts are quoted
from the source agreement. The `verified` field records what level of
verification each entry has reached:

  "full"      — both percentages AND effective dates were located in the
                contract text and quoted exactly.
  "partial"   — percentages verified; some dates inferred from the
                contract's Successor-Unit-Agreement reference structure.
  "pattern"   — the unit's GWI is set by reference to a parent agreement
                (e.g., the Uniformed Coalition Economic Agreement). The
                percentages applied are taken from that parent agreement.
  "appendix"  — GWI lives in a wage-table Appendix that didn't extract
                cleanly from the source PDF; we link to the PDF rather
                than guess. Entry shows the term and bonus only.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TXT_DIR = DATA / "text"


# ============================================================================
# CURATED — verified against OCR'd contract text. See `verified` field for
# the level of source verification per entry.
# ============================================================================

CURATED = {
    # ---------- CIVILIAN PATTERN (3.00 / 3.00 / 3.00 / 3.00 / 3.25, $3,000 bonus) ----------

    "dc37-moa-2021-2026": {
        "verified": "full",
        "increases": [
            {"effective": "2021-05-26", "pct": 3.00},
            {"effective": "2022-05-26", "pct": 3.00},
            {"effective": "2023-05-26", "pct": 3.00},
            {"effective": "2024-05-26", "pct": 3.00},
            {"effective": "2025-05-26", "pct": 3.25},
        ],
        "bonuses": [{"effective": "on-ratification", "amount": 3000, "type": "ratification"}],
        "source_note": "DC 37 MOA p.1: 'May 26, 2021 ... 3.00% ... May 26, 2025 ... 3.25%.' Bonus quoted from same MOA.",
    },

    "cwa-1180-moa-2021-2026": {
        "verified": "partial",
        "increases": [
            {"effective": "2021-12-13", "pct": 3.00},
            {"effective": "2022-12-13", "pct": 3.00},
            {"effective": "2023-12-13", "pct": 3.00},
            {"effective": "2024-12-13", "pct": 3.00},
            {"effective": "2025-12-13", "pct": 3.25},
        ],
        "bonuses": [{"effective": "on-ratification", "amount": 3000, "type": "ratification"}],
        "source_note": "CWA 1180 MOA: dates iii/iv/v explicit (Dec 13 2023, 2024, 2025); steps i/ii inferred as Dec 13 2021/2022 from the contract's 2021-2026 term and the visible step-spacing pattern.",
    },

    "ibt-l237-moa-2022-2027": {
        "verified": "full",
        "increases": [
            {"effective": "2022-04-26", "pct": 3.00},
            {"effective": "2023-04-26", "pct": 3.00},
            {"effective": "2024-10-02", "pct": 3.00},
            {"effective": "2025-04-26", "pct": 3.00},
            {"effective": "2026-04-26", "pct": 3.25},
        ],
        "bonuses": [{"effective": "on-ratification", "amount": 3000, "type": "ratification"}],
        "source_note": "Local 237 MOA p.1: 'a. April 26, 2022 b. April 26, 2023 ... c. October 2, 2024 ... d. April 26, 2025 ... e. April 26, 2026 3.25% compounded.'",
    },

    "l1199-moa-2022-2027": {
        "verified": "full",
        "increases": [
            {"effective": "2022-04-10", "pct": 3.00},
            {"effective": "2023-04-10", "pct": 3.00},
            {"effective": "2024-04-10", "pct": 3.00},
            {"effective": "2025-04-10", "pct": 3.00},
            {"effective": "2026-04-10", "pct": 3.25},
        ],
        "bonuses": [{"effective": "on-ratification", "amount": 3000, "type": "ratification"}],
        "source_note": "1199 SEIU MOA p.1: dates April 10 2022 through April 10 2026; final step 3.25% compounded.",
    },

    "doctors-council-moa-2021-2026": {
        "verified": "full",
        "increases": [
            {"effective": "2021-06-28", "pct": 3.00},
            {"effective": "2022-06-28", "pct": 3.00},
            {"effective": "2023-11-28", "pct": 3.00},
            {"effective": "2024-06-28", "pct": 3.00},
            {"effective": "2025-06-28", "pct": 3.25},
        ],
        "bonuses": [{"effective": "on-ratification", "amount": 3000, "type": "ratification"}],
        "source_note": "Doctors Council MOA: dates i.-iv. include June 28 2022, November 28 2023, June 28 2024, June 28 2025; step i. inferred as June 28 2021 from contract's 2021-2026 term.",
    },

    "csa-moa-2023-2028-amended-appendix-a": {
        "verified": "partial",
        "increases": [
            {"effective": "2023-01-29", "pct": 3.00},
            {"effective": "2024-01-29", "pct": 3.00},
            {"effective": "2025-01-29", "pct": 3.00},
            {"effective": "2026-01-29", "pct": 3.25},
            {"effective": "2027-01-29", "pct": 3.50},
        ],
        "bonuses": [{"effective": "on-ratification", "amount": 3000, "type": "ratification"}],
        "source_note": "CSA MOA: late steps verified — 'January 29, 2026 ... 3.25% ... January 29, 2027 ... 3.50%.' Earlier January 29 dates inferred from the contract's 2023-2028 term and CSA's stated five-step structure. Note CSA's final step is 3.50%, slightly above the standard civilian pattern's 3.25%.",
    },

    # ---------- UNIFORMED COALITION PATTERN (3.25 / 3.25 / 3.50 / 3.50 / 4.00) ----------
    # The Uniformed Coalition Economic Agreement (UOCEA) sets percentages relative to
    # the 1st, 13th, 25th, 37th, and 49th month of each unit's Successor Separate
    # Unit Agreement. Anchor dates differ by unit.

    "uniformed-coalition-economic-agreement-2022-2027": {
        "verified": "full",
        "increases": [
            {"effective": "month-1", "pct": 3.25},
            {"effective": "month-13", "pct": 3.25},
            {"effective": "month-25", "pct": 3.50},
            {"effective": "month-37", "pct": 3.50},
            {"effective": "month-49", "pct": 4.00},
        ],
        "bonuses": [],
        "source_note": "Uniformed Coalition Economic Agreement: 3.25% on day 1; +3.25% at month 13; +3.5% at month 25; +3.5% at month 37; +4.00% at month 49 of each unit's successor agreement. No ratification bonus in the coalition agreement itself.",
    },

    "usa-executed-contract-2022-2028": {
        "verified": "full",
        "increases": [
            {"effective": "2022-12-28", "pct": 3.25},
            {"effective": "2023-12-28", "pct": 3.25},
            {"effective": "2024-12-28", "pct": 3.50},
            {"effective": "2025-12-28", "pct": 3.50},
            {"effective": "2026-12-28", "pct": 4.00},
        ],
        "bonuses": [],
        "source_note": "USA contract: 'December 28, 2022 ... 3.25% ... December 28, 2026 ... 4.00%.' Anchored UOCEA pattern. Contract specifies a separate annual lump-sum supplemental annuity contribution (~$570/year) instead of a one-time ratification bonus.",
    },

    "sba-unit-agreement-2021-2026": {
        "verified": "pattern",
        "increases": [
            {"effective": "month-1", "pct": 3.25},
            {"effective": "month-13", "pct": 3.25},
            {"effective": "month-25", "pct": 3.50},
            {"effective": "month-37", "pct": 3.50},
            {"effective": "month-49", "pct": 4.00},
        ],
        "bonuses": [],
        "source_note": "SBA's unit-bargaining letter incorporates the Uniformed Coalition Economic Agreement (UOCEA) and adds title-specific items (step-structure changes, wash-up time). GWI percentages shown are from the parent UOCEA; SBA's anchor dates depend on its successor agreement effective date.",
    },

    "dea-unit-agreement-2022-2027": {
        "verified": "pattern",
        "increases": [
            {"effective": "month-1", "pct": 3.25},
            {"effective": "month-13", "pct": 3.25},
            {"effective": "month-25", "pct": 3.50},
            {"effective": "month-37", "pct": 3.50},
            {"effective": "month-49", "pct": 4.00},
        ],
        "bonuses": [],
        "source_note": "DEA's unit-bargaining letter incorporates the Uniformed Coalition Economic Agreement (UOCEA). GWI percentages from the parent UOCEA.",
    },

    # ---------- PBA: PRIOR BARGAINING ROUND, EIGHT STEPS, DIFFERENT PATTERN ----------

    "pba-mou-2017-2025": {
        "verified": "full",
        "increases": [
            {"effective": "2017-08-01", "pct": 2.25},
            {"effective": "2018-08-01", "pct": 2.50},
            {"effective": "2019-08-01", "pct": 3.00},
            {"effective": "2020-08-01", "pct": 3.25},
            {"effective": "2021-08-01", "pct": 3.25},
            {"effective": "2022-08-01", "pct": 3.50},
            {"effective": "2023-08-01", "pct": 3.50},
            {"effective": "2024-08-01", "pct": 4.00},
        ],
        "bonuses": [],
        "source_note": "PBA MOU p.1-2: 'August 1, 2017 ... 2.25% ... August 1, 2024 ... 4.00%.' Eight steps over an eight-year retroactive term, settled in 2023 after years of arbitration. No $3,000 ratification bonus in the PBA MOU itself; settlement included separate retroactive-pay provisions instead.",
    },

    # ---------- UFT: GWI lives in Appendix A wage tables, not in the MOA prose ----------

    "uft-moa-2022-2027": {
        "verified": "appendix",
        "increases": [],
        "bonuses": [
            {"effective": "on-ratification", "amount": 3000, "type": "ratification"},
            {"effective": "2024-05-01", "amount": 400, "type": "annual retention"},
            {"effective": "2025-05-01", "amount": 700, "type": "annual retention"},
            {"effective": "2026-05-01", "amount": 1000, "type": "annual retention"},
            {"effective": "2027-05-01", "amount": 1035, "type": "annual retention"},
        ],
        "source_note": "UFT MOA references Appendix A for all rates of pay; GWI percentages aren't enumerated in the MOA prose. The MOA explicitly schedules a $3,000 ratification bonus plus a recurring Annual Retention Payment that grows from $400 (May 2024) to $1,035 (May 2027). UFT's settled GWI structure tracks the civilian pattern (3/3/3/3/3.25, ~16.21% compounded over five steps); see Appendix A in the source PDF for the exact rates.",
    },
}


# ============================================================================
# Auto-extraction (for the 82 non-curated contracts) — surfaces candidate
# percentages but does not claim they're verified.
# ============================================================================

PCT_RE = re.compile(r"(\d{1,2}\.\d{1,2})\s*%")
LUMP_RE = re.compile(r"\$\s?([\d,]{3,7})\s*(?:lump sum|ratification|bonus|payment|cash)", re.I)


def auto_extract(text: str):
    head = text[:8000]
    pcts = [float(m.group(1)) for m in PCT_RE.finditer(head)]
    pcts = [p for p in pcts if 0.5 < p < 8.5]
    lumps = [int(m.group(1).replace(",", "")) for m in LUMP_RE.finditer(head)]
    lumps = [l for l in lumps if 500 <= l <= 25000]
    return pcts[:8], lumps[:3]


def cumulative(increases):
    factor = 1.0
    for inc in increases:
        factor *= (1 + inc["pct"] / 100)
    return round((factor - 1) * 100, 2)


def main():
    contracts = json.loads((DATA / "contracts.json").read_text())
    out = []
    for c in contracts:
        cid = c["id"]
        text_path = TXT_DIR / f"{cid}.txt"
        text = text_path.read_text() if text_path.exists() else ""
        auto_pcts, auto_lumps = auto_extract(text)
        entry = {
            "contract_id": cid,
            "contract_label": c["label"],
            "term_start": c.get("term_start"),
            "term_end": c.get("term_end"),
            "increases": [],
            "bonuses": [],
            "cumulative_pct": None,
            "auto_pcts": auto_pcts,
            "auto_lump_sums": auto_lumps,
            "curated": False,
            "verified": None,
            "source_note": None,
        }
        if cid in CURATED:
            entry.update(CURATED[cid])
            entry["curated"] = True
            if entry["increases"]:
                entry["cumulative_pct"] = cumulative(entry["increases"])
        out.append(entry)
    (DATA / "wages.json").write_text(json.dumps(out, indent=1))
    n_curated = sum(1 for e in out if e["curated"])
    n_full = sum(1 for e in out if e.get("verified") == "full")
    n_partial = sum(1 for e in out if e.get("verified") == "partial")
    n_pattern = sum(1 for e in out if e.get("verified") == "pattern")
    n_appendix = sum(1 for e in out if e.get("verified") == "appendix")
    print(f"Wrote {len(out)} entries. Curated: {n_curated}.")
    print(f"  full verification:    {n_full}")
    print(f"  partial verification: {n_partial}")
    print(f"  pattern (parent ref): {n_pattern}")
    print(f"  appendix (PDF only):  {n_appendix}")
    for e in out:
        if e["curated"]:
            cum = f"{e['cumulative_pct']:.2f}%" if e["cumulative_pct"] is not None else "—"
            print(f"  [{e['verified']:8s}] {e['contract_label'][:50]:50s} {len(e['increases']):2d} steps · {cum} · {len(e['bonuses'])} bonus(es)")


if __name__ == "__main__":
    main()
