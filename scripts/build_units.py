"""Build data/units.json — bargaining-unit metadata per contract.

For each contract:
  - sector (uniformed / education / health / clerical / skilled-trades / professional / managerial / other)
  - union_full / local / employer (from label + curated lookup)
  - summary (from recognition clause where present, else label-derived stub)
  - headcount + headcount_source (curated for major unions; null for the rest)
  - titles (extracted from recognition clause where present)
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Curated entries for the largest / best-known bargaining units.
# Headcounts are approximate, sourced from cited public documents.
# Where no public source is currently linked, headcount is null.
CURATED = {
    "uft-moa-2022-2027": {
        "union_full": "United Federation of Teachers (UFT), Local 2, AFT, AFL-CIO",
        "local": "Local 2",
        "employer": "NYC Department of Education / Board of Education",
        "sector": "education",
        "headcount": 120000,
        "headcount_note": "~120,000 covered employees including teachers, paraprofessionals, school secretaries, guidance counselors, etc., per UFT public statements and DOE budget testimony.",
        "summary": "The largest single bargaining unit in NYC government. Covers DOE teachers, paraprofessionals, school secretaries, guidance counselors, social workers, psychologists, attendance teachers, lab specialists, and related school-based titles.",
        "titles": ["Teacher", "Paraprofessional", "School Secretary", "Guidance Counselor", "Social Worker", "School Psychologist", "Educational Assistant", "Lab Specialist"],
    },
    "dc37-moa-2021-2026": {
        "union_full": "American Federation of State, County and Municipal Employees (AFSCME), District Council 37, AFL-CIO",
        "local": "DC 37 (umbrella for ~50 affiliated locals)",
        "employer": "City of New York (mayoral agencies, HHC, NYCHA, CUNY, libraries)",
        "sector": "clerical-and-professional",
        "headcount": 125000,
        "headcount_note": "~125,000 active members across 50+ locals, per DC 37 public statements.",
        "summary": "The largest public-employee union in NYC. The DC 37 economic agreement sets wage pattern for ~50 affiliated locals covering clerical, technical, custodial, library, school-support, and professional titles across mayoral agencies, HHC, NYCHA, CUNY, and the public libraries.",
        "titles": ["Office Aide", "Clerical Associate", "Caseworker", "Eligibility Specialist", "Custodian", "School Aide", "Special Officer", "Accountant", "Computer Associate"],
    },
    "pba-mou-2017-2025": {
        "union_full": "Patrolmen's Benevolent Association of the City of New York (PBA NYC)",
        "local": "PBA",
        "employer": "NYC Police Department",
        "sector": "uniformed-police",
        "headcount": 24000,
        "headcount_note": "~24,000 active police officers, per NYPD published headcount and PBA public statements.",
        "summary": "Represents all rank-and-file NYPD police officers below the rank of sergeant. Sets the floor of NYC's uniformed-pattern bargaining; other uniformed unions (SBA, DEA, LBA, CEA) typically settle in line with PBA.",
        "titles": ["Police Officer"],
    },
    "uniformed-coalition-economic-agreement-2022-2027": {
        "union_full": "Uniformed Coalition (multi-union umbrella: UFA, UFOA, COBA, ADWA, USCA, USA, etc.)",
        "local": "Multiple uniformed locals",
        "employer": "City of New York (NYPD, FDNY, DOC, DSNY)",
        "sector": "uniformed-pattern",
        "headcount": None,
        "headcount_note": "Coalition-level economic terms; underlying individual unit agreements set unit-specific headcounts.",
        "summary": "The economic-pattern agreement that sets wage increases and lump sums for the city's uniformed forces collectively (Fire, Sanitation, Correction). Each underlying unit then negotiates a unit-specific agreement that incorporates these terms.",
        "titles": [],
    },
    "usa-executed-contract-2022-2028": {
        "union_full": "Uniformed Sanitationmen's Association, Local 831 IBT",
        "local": "Local 831",
        "employer": "NYC Department of Sanitation",
        "sector": "uniformed-sanitation",
        "headcount": 7000,
        "headcount_note": "~7,000 sanitation workers per DSNY headcount data; LSA reports similar figures.",
        "summary": "Represents all uniformed sanitation workers below supervisor rank — the core of DSNY's collection, plowing, and street-cleaning workforce.",
        "titles": ["Sanitation Worker"],
    },
    "csa-moa-2023-2028-amended-appendix-a": {
        "union_full": "Council of School Supervisors and Administrators (CSA), Local 1 AFSA, AFL-CIO",
        "local": "Local 1 AFSA",
        "employer": "NYC Department of Education",
        "sector": "education-management",
        "headcount": 6500,
        "headcount_note": "~6,500 school-based supervisors per CSA public statements.",
        "summary": "Represents NYC public school principals, assistant principals, education administrators, and supervisors. The supervisory counterpart to UFT.",
        "titles": ["Principal", "Assistant Principal", "Supervisor", "Education Administrator"],
    },
    "ibt-l237-moa-2022-2027": {
        "union_full": "International Brotherhood of Teamsters, Local 237",
        "local": "Local 237",
        "employer": "NYC (NYCHA, DOE School Safety, NYPD School Safety, multiple agencies)",
        "sector": "clerical-and-special-officer",
        "headcount": 24000,
        "headcount_note": "~24,000 city employees represented across multiple titles per Local 237 public statements.",
        "summary": "Covers a broad set of city titles — School Safety Agents, Special Officers, NYCHA Caretakers and Housing Assistants, Bricklayers, Public Health Nurses, Bridge Repairers, and others.",
        "titles": ["School Safety Agent", "Special Officer", "Housing Assistant", "Bricklayer", "Bridge Repairer", "Public Health Nurse"],
    },
    "cwa-1180-moa-2021-2026": {
        "union_full": "Communications Workers of America, Local 1180, AFL-CIO",
        "local": "Local 1180",
        "employer": "City of New York (multiple agencies)",
        "sector": "supervisory-clerical",
        "headcount": 8000,
        "headcount_note": "~8,000 supervisory administrative titles per CWA Local 1180 public statements.",
        "summary": "Represents Administrative Managers, Principal Administrative Associates, and other supervisory clerical titles across mayoral agencies. Settled a major pay-equity arbitration in 2018.",
        "titles": ["Administrative Manager", "Principal Administrative Associate", "Administrative Staff Analyst"],
    },
    "sba-unit-agreement-2021-2026": {
        "union_full": "Sergeants Benevolent Association of the City of New York (SBA)",
        "local": "SBA",
        "employer": "NYC Police Department",
        "sector": "uniformed-police",
        "headcount": 4500,
        "headcount_note": "~4,500 NYPD sergeants per SBA / NYPD public statements.",
        "summary": "Represents all NYPD sergeants. Negotiates separately from PBA but typically pegs increases to PBA's pattern.",
        "titles": ["Sergeant"],
    },
    "dea-unit-agreement-2022-2027": {
        "union_full": "NYC Detectives' Endowment Association",
        "local": "DEA",
        "employer": "NYC Police Department",
        "sector": "uniformed-police",
        "headcount": 6000,
        "headcount_note": "~6,000 NYPD detectives per DEA public statements.",
        "summary": "Represents NYPD detectives of all grades.",
        "titles": ["Detective"],
    },
    "l1199-moa-2022-2027": {
        "union_full": "1199 SEIU United Healthcare Workers East",
        "local": "1199 SEIU",
        "employer": "NYC Health + Hospitals",
        "sector": "health",
        "headcount": 2500,
        "headcount_note": "~2,500 caregivers in 1199 SEIU's citywide City / H+H bargaining unit, per 1199 settlement announcements. (The larger 1199 figures cited publicly cover its private voluntary-hospital contracts, not NYC employment.)",
        "summary": "Represents non-RN healthcare workers at NYC Health + Hospitals — patient care assistants, dietary, environmental services, technical and professional titles. (Not to be confused with 1199's much larger private-sector NYC membership.)",
        "titles": ["Patient Care Associate", "Dietary Aide", "Environmental Services Aide", "Pharmacy Technician"],
    },
    "ufa-moa-2017-2020": {
        "union_full": "Uniformed Firefighters Association of Greater New York (UFA), IAFF Local 94",
        "local": "IAFF Local 94",
        "employer": "NYC Fire Department",
        "sector": "uniformed-fire",
        "headcount": 8500,
        "headcount_note": "~8,500 active FDNY firefighters (8,533 filled in the Firefighter title as of 10/10/2025), per the FDNY Fire Workforce Analysis published by the NYC Council Finance Division. UFA's own site rounds to ~9,000.",
        "summary": "Represents all NYC firefighters below officer rank. UFA contracts in NYC have historically come out of impasse arbitration. Most recent published contract on OLR is the 2017-2020 MOA; economic terms for the 2022-2027 cycle are set by the Uniformed Coalition Economic Agreement (also in this corpus).",
        "titles": ["Firefighter", "Fire Marshal", "Wiper", "Pilot", "Marine Engineer (FDNY)"],
    },
    "ufoa-fire-officers-2018-2021": {
        "union_full": "Uniformed Fire Officers Association (UFOA), IAFF Local 854",
        "local": "IAFF Local 854",
        "employer": "NYC Fire Department",
        "sector": "uniformed-fire",
        "headcount": 2400,
        "headcount_note": "~2,400 active FDNY fire officers (lieutenants, captains, battalion and deputy chiefs, medical officers and supervising fire marshals; 2,406 filled as of 10/10/2025), per the FDNY Fire Workforce Analysis (NYC Council Finance Division).",
        "summary": "Represents FDNY lieutenants, captains, battalion chiefs, deputy chiefs, fire medical officers, and supervising fire marshals. Most recent published contract on OLR is the 2018-2021 Fire Officers Agreement; economic terms for the 2022-2027 cycle are set by the Uniformed Coalition Economic Agreement.",
        "titles": ["Lieutenant", "Captain", "Battalion Chief", "Deputy Chief", "Fire Medical Officer", "Supervising Fire Marshal"],
    },
    "nysna-staff-nurses-2019-2023": {
        "union_full": "New York State Nurses Association (NYSNA)",
        "local": "NYSNA",
        "employer": "NYC Health + Hospitals (Mayoral)",
        "sector": "health",
        "headcount": 8000,
        "headcount_note": "~8,000 RNs across NYC H+H facilities and mayoral agencies, per NYSNA's 2023 pay-parity contract announcement (July 31, 2023). Not an H+H-only subtotal.",
        "summary": "Represents registered nurses at NYC Health + Hospitals (the City's public hospital system) and the Mayoral / civilian workforce. Most recent published contract on OLR is the 2019-2023 Staff Nurses Agreement; the historic 2023+ pay-parity successor agreement (announced July 2023) is not yet posted on OLR at time of corpus build.",
        "titles": ["Staff Nurse", "Nurse Practitioner", "Clinical Nurse Specialist", "Nurse Manager"],
    },
    "psc-cuny-moa-2023-2027": {
        "union_full": "Professional Staff Congress of CUNY (PSC), AFT Local 2334",
        "local": "AFT Local 2334",
        "employer": "City University of New York (CUNY)",
        "sector": "education",
        "headcount": 30000,
        "headcount_note": "~30,000 faculty and professional staff at CUNY per PSC public statements.",
        "summary": "Represents full-time and adjunct faculty, professional staff, and graduate-employee teaching assistants across the City University of New York. Bargains directly with CUNY (a state-affiliated entity), not through NYC OLR. The 2023-2027 MOA modifies the underlying 2017-2023 PSC-CUNY agreement (also in this corpus).",
        "titles": ["Professor", "Associate Professor", "Assistant Professor", "Lecturer", "Adjunct Faculty", "Higher Education Officer", "College Lab Technician", "Graduate Assistant"],
    },
    "psc-cuny-agreement-2017-2023": {
        "union_full": "Professional Staff Congress of CUNY (PSC), AFT Local 2334",
        "local": "AFT Local 2334",
        "employer": "City University of New York (CUNY)",
        "sector": "education",
        "headcount": 30000,
        # Same ~30,000 PSC members as the 2023-2027 MOA entry. Both documents
        # cover one population, so this one is excluded from the site-wide
        # covered-employee total to avoid double-counting.
        "headcount_duplicate_of": "psc-cuny-moa-2023-2027",
        "headcount_note": "~30,000 faculty and professional staff at CUNY per PSC public statements. This is the same population covered by the 2023-2027 PSC-CUNY MOA, not an additional 30,000; it is counted once in the site-wide total.",
        "summary": "Underlying 2017-2023 collective bargaining agreement between CUNY and PSC, modified by the 2023-2027 MOA (also in this corpus). Provides the full text of articles on workload, academic freedom, governance, grievance, and other non-economic provisions that the MOA does not re-state.",
        "titles": ["Professor", "Associate Professor", "Assistant Professor", "Lecturer", "Adjunct Faculty", "Higher Education Officer", "College Lab Technician", "Graduate Assistant"],
    },
    "deputy-sheriffs-moa-2022-2027": {
        "union_full": "New York City Deputy Sheriffs Benevolent Association",
        "local": "Deputy Sheriffs Benevolent Association",
        "employer": "City of New York (Sheriff's Office, Department of Finance)",
        "sector": "other",
        "headcount": None,
        "headcount_note": None,
        "summary": "Covers Deputy Sheriffs (Level I) in the New York City Sheriff's Office, the civil-enforcement arm of the Department of Finance. The 2022-2027 MOA, dated July 2026, applies the uniformed-coalition wage pattern (3.25/3.25/3.5/3.5/4.0) over a 62-month term and sets a new Level I salary schedule effective January 1, 2025.",
        "titles": ["Deputy Sheriff"],
    },
    "doctors-council-moa-2021-2026": {
        "union_full": "Doctors Council, SEIU Local 10MD",
        "local": "Doctors Council / SEIU Local 10MD",
        "employer": "NYC Health + Hospitals + multiple city agencies",
        "sector": "health-professional",
        "headcount": 500,
        "headcount_note": "~500 city-employed physicians (NYC H+H, DOHMH, and OCME medical examiners) covered by this Doctors Council public-sector MOA, per the NYC Mayor's Office (Dec 16, 2024). A separate ~2,500 attending physicians at H+H are employed by affiliate groups (PAGNY, Mount Sinai, NYU) and bargain outside this agreement.",
        "summary": "Represents salaried physicians and dentists working for the City — at H+H, NYC DOHMH, DOC, and other agencies.",
        "titles": ["Physician", "Senior Physician", "Dentist"],
    },
}

# Sector classification keywords (applied in order; first match wins)
SECTOR_RULES = [
    (r"\bpolice\b|\bpba\b|\bsba\b|\bdea\b|\blba\b|\bcea\b|sergeants?|detectives?|lieutenants?|captains?", "uniformed-police"),
    (r"\bfire\b|\bufa\b|\bufoa\b|firefighters?|fire officers?", "uniformed-fire"),
    (r"\bsanitation\b|\bdsna\b|\busa\b|\busca\b|\busa-", "uniformed-sanitation"),
    (r"\bcorrection\b|\bcoba\b|\badwa\b|\bcoba\b|\badba\b", "uniformed-correction"),
    (r"\bteacher\b|\buft\b|\bcsa\b|\bcsba\b|principal|school", "education"),
    (r"\bdoctor|physician|dental|nurse|hospital|medical|health|1199|doctors council", "health"),
    (r"\binspector\b|\bdetective\b|investigat", "professional"),
    (r"electrician|carpenter|plumber|painter|machinist|mechanic|welder|engineer|trades?|steamfitter|boilermaker|locksmith|blacksmith|laborer|repairer|fitter|operator|crane|gasoline|sheet metal|sign|rigger|dockbuilder|ship", "skilled-trades"),
    (r"\battorney\b|\blawyer\b|\bale\b|legislative", "professional"),
    (r"\bdc37\b|\bdc 37\b|\bdistrict council 37\b|\blocal 37\b|\blocal 372\b|\blocal 1549\b|\blocal 983\b", "clerical-and-professional"),
    (r"administrative manager|administrative associate|cwa 1180|supervisory|managerial|managers", "supervisory-clerical"),
]


def classify(label: str) -> str:
    s = label.lower()
    for rx, sector in SECTOR_RULES:
        if re.search(rx, s):
            return sector
    return "other"


def auto_summary(contract, recog_text: str | None) -> str:
    if recog_text:
        # First sentence of the recognition clause if it's coherent
        first = re.split(r"(?<=[.\n])\s+", recog_text.strip(), maxsplit=1)[0]
        if 30 < len(first) < 320:
            return first
    label = contract["label"]
    return f"{label} — see contract for the full recognition clause defining covered titles."


def find_recognition_text(clauses, contract_id) -> str | None:
    # Best candidates: clauses whose heading contains "recognition" / "bargaining unit"
    candidates = []
    for c in clauses:
        if c["contract_id"] != contract_id:
            continue
        h = (c.get("heading") or "").lower()
        if "recognition" in h or "bargaining unit" in h or "preamble" in h or "recogni" in h:
            candidates.append(c)
    if candidates:
        # Pick the longest meaningful one
        candidates.sort(key=lambda x: -len(x.get("text") or ""))
        return candidates[0]["text"]
    # Fallback: scan first clause text for "recognized" pattern
    for c in clauses:
        if c["contract_id"] != contract_id:
            continue
        t = (c.get("text") or "")[:1500]
        if re.search(r"recogni[sz]e[ds]?\s+as|hereby recognized|exclusive (collective )?bargaining representative", t, re.I):
            return t
        break
    return None


def main():
    contracts = json.loads((DATA / "contracts.json").read_text())
    clauses = json.loads((DATA / "clauses.json").read_text())
    units = []
    for c in contracts:
        cid = c["id"]
        recog_text = find_recognition_text(clauses, cid)
        entry = {
            "contract_id": cid,
            "contract_label": c["label"],
            "term_start": c.get("term_start"),
            "term_end": c.get("term_end"),
            "sector": classify(c["label"]),
            "union_full": None,
            "local": None,
            "employer": None,
            "headcount": None,
            "headcount_note": None,
            "summary": auto_summary(c, recog_text),
            "titles": [],
            "curated": False,
        }
        if cid in CURATED:
            entry.update(CURATED[cid])
            entry["curated"] = True
        units.append(entry)

    (DATA / "units.json").write_text(json.dumps(units, indent=1))
    n_curated = sum(1 for u in units if u["curated"])
    n_with_head = sum(1 for u in units if u["headcount"])
    print(f"Wrote {len(units)} bargaining units. Curated: {n_curated}. Headcount populated: {n_with_head}.")
    by_sector = {}
    for u in units:
        by_sector[u["sector"]] = by_sector.get(u["sector"], 0) + 1
    for s, n in sorted(by_sector.items(), key=lambda x: -x[1]):
        print(f"  {n:3d}  {s}")


if __name__ == "__main__":
    main()
