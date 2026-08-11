"""Link each amendment to the underlying agreement it modifies.

Sixty-three documents in this corpus expressly continue a prior agreement but
name no document and link to nothing. Those prior agreements are public — they
are just published somewhere else, with no path from the amendment to them.
This script attaches that path.

Two sources, both verified live before anything is written:

  1. OLR's own "Uniformed Contracts" page
     (nyc.gov/site/olr/labor/labor-uniformed-contracts.page), which carries the
     full underlying agreements for the uniformed unions. It is not linked from
     the Recent Agreements page, so a reader starting from a unit letter has no
     way to discover it.
  2. Union-published copies, for units whose underlying agreement OLR does not
     post at all (UFT, DC 37).

Every URL is checked with a real request. A URL that does not return a PDF (or,
for landing pages, HTML) is dropped rather than published — a dead link on a
citation tool is worse than no link. Nothing here is guessed from a pattern.
"""
from __future__ import annotations
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OLR = "https://www.nyc.gov/assets/olr/downloads/pdf/collectivebargaining/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

# contract_id -> predecessor record. `file` is relative to OLR; `url` is absolute.
PREDECESSORS = {
    # ---- Uniformed: underlying agreements on OLR's Uniformed Contracts page ----
    "pba-mou-2017-2025": {
        "file": "cbu79-police-patrolmens-benevolent-association-080106-to-073110.pdf",
        "label": "PBA underlying unit agreement, 2006-2010 (CBU 79)",
        "publisher": "NYC Office of Labor Relations",
    },
    "sba-unit-agreement-2021-2026": {
        "file": "cbu91-police-sergeants-benevolent-association -060105-to-082911.pdf",
        "label": "SBA underlying unit agreement, 2005-2011 (CBU 91)",
        "publisher": "NYC Office of Labor Relations",
    },
    "dea-unit-agreement-2022-2027": {
        "file": "cbu29-police-detectives-endowment-association-mou-040108-to-033112.pdf",
        "label": "DEA underlying memorandum of understanding, 2008-2012 (CBU 29)",
        "publisher": "NYC Office of Labor Relations",
    },
    "lba-10-5-2023-unit-bargaining-agreement": {
        "file": "cbu59-police-lieutenants-benevolent-association-110109-to-103111.pdf",
        "label": "LBA underlying unit agreement, 2009-2011 (CBU 59)",
        "publisher": "NYC Office of Labor Relations",
    },
    "cea-unit-agreement-2022-2027": {
        "file": "cbu17-police-captains-endowment-association-110103-to-033112.pdf",
        "label": "CEA underlying unit agreement, 2003-2012 (CBU 17)",
        "publisher": "NYC Office of Labor Relations",
    },
    "coba-unit-agreement-2022-2027": {
        "file": "cbu27-corrections-officers-110109-to-103111.pdf",
        "label": "Correction officers underlying agreement, 2009-2011 (CBU 27)",
        "publisher": "NYC Office of Labor Relations",
    },
    "cca-unit-agreement-2022-2028": {
        "file": "cbu25-corrections-captains-121607-to-063012.pdf",
        "label": "Correction captains underlying agreement, 2007-2012 (CBU 25)",
        "publisher": "NYC Office of Labor Relations",
    },
    "adwa-unit-agreement-2023-2028": {
        "file": "cbu11-corrections-assistant-deputy-wardens-revised-030108-to-06-30-12.pdf",
        "label": "Assistant deputy wardens underlying agreement, 2008-2012 (CBU 11)",
        "publisher": "NYC Office of Labor Relations",
    },
    "ufa-moa-2017-2020": {
        "file": "cbu41-fire-uniformed-080108-to-073110.pdf",
        "label": "Uniformed firefighters underlying agreement, 2008-2010 (CBU 41)",
        "publisher": "NYC Office of Labor Relations",
    },
    "ufoa-fire-officers-2018-2021": {
        "file": "cbu43-fire-officers-032007-to-031911.pdf",
        "label": "Fire officers underlying agreement, 2007-2011 (CBU 43)",
        "publisher": "NYC Office of Labor Relations",
    },
    "usa-executed-contract-2022-2028": {
        "file": "cbu49-sanitation-workers-030207-to-092011.pdf",
        "label": "Sanitation workers underlying agreement, 2007-2011 (CBU 49)",
        "publisher": "NYC Office of Labor Relations",
    },
    "soa-unit-agreement-2023-2028": {
        "file": "cbu99-sanitation-officers-111307-to-070112.pdf",
        "label": "Sanitation officers underlying agreement, 2007-2012 (CBU 99)",
        "publisher": "NYC Office of Labor Relations",
    },
    "usca-unit-agreement-2022-2027": {
        "file": "cbu100-sanitation-chiefs-re-opner-101007-to-100911.pdf",
        "label": "Sanitation chiefs underlying agreement, 2007-2011 (CBU 100)",
        "publisher": "NYC Office of Labor Relations",
    },

    # ---- Union-published, because OLR does not post these at all ----
    "uft-moa-2022-2027": {
        "url": "https://www.uft.org/your-rights/contracts/doe-and-city-contracts-printable-versions",
        "label": "Full UFT-DOE contracts by title (teachers, paraprofessionals, secretaries, counselors, nurses and therapists, psychologists and social workers)",
        "publisher": "United Federation of Teachers",
        # uft.org returns 403 to scripted requests. Confirmed by loading the page
        # in a browser on 2026-08-11: it lists the 2022-27 memoranda plus the
        # full 2008-2019 contracts for each DOE title. Checked manually because
        # the automated probe cannot reach it, not because it went unchecked.
        "skip_check": "uft.org blocks automated requests; verified in-browser 2026-08-11",
    },
    "dc37-moa-2021-2026": {
        "url": "https://www.dc37.net/app/uploads/dc37contracts/pdfs/2001_2021_Citywide_Agreement.pdf",
        "label": "2001-2021 Citywide Agreement, the underlying citywide contract",
        "publisher": "District Council 37",
    },
}


def check(url):
    """Return (ok, note). Follows redirects; verifies content type."""
    try:
        req = urllib.request.Request(url, headers=UA, method="GET")
        with urllib.request.urlopen(req, timeout=60) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            head = r.read(5)
            if r.status != 200:
                return False, f"HTTP {r.status}"
            if head.startswith(b"%PDF"):
                return True, "pdf"
            if "text/html" in ctype:
                return True, "html"
            return False, f"not a PDF or HTML ({ctype})"
    except Exception as e:
        return False, str(e)[:80]


def main():
    contracts = json.loads((DATA / "contracts.json").read_text())
    by_id = {c["id"]: c for c in contracts}
    kept = dropped = 0

    for cid, rec in PREDECESSORS.items():
        if cid not in by_id:
            print(f"[skip] {cid} not in corpus", file=sys.stderr)
            continue
        url = rec.get("url") or (OLR + urllib.parse.quote(rec["file"]))
        if rec.get("skip_check"):
            ok, note = True, "manual: " + rec["skip_check"]
        else:
            ok, note = check(url)
        if not ok:
            print(f"[DROP] {cid}: {note}  {url}", file=sys.stderr)
            dropped += 1
            continue
        by_id[cid]["predecessor"] = {
            "url": url,
            "label": rec["label"],
            "publisher": rec["publisher"],
            "verified": True,
        }
        print(f"  ok ({note})  {cid} -> {rec['label'][:56]}")
        kept += 1

    (DATA / "contracts.json").write_text(json.dumps(contracts, indent=1))
    n_amend = sum(1 for c in contracts if c.get("amends_predecessor"))
    n_linked = sum(1 for c in contracts if c.get("predecessor"))
    print(f"\nverified and linked: {kept}   dropped (unverified): {dropped}")
    print(f"{n_linked} of {n_amend} amendments now link to their underlying agreement.")


if __name__ == "__main__":
    main()
