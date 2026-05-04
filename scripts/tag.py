"""Apply topic tags to each clause in data/clauses.json (in place).

Topics use keyword matching against heading + body. A clause can have multiple tags.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# {topic: list of regex patterns (case-insensitive)}
TOPICS = {
    "wages": [r"\bwage(s)?\b", r"\bsalar(y|ies)\b", r"\bgeneral wage increase\b", r"\bcompensation\b", r"\brates? of pay\b"],
    "longevity": [r"\blongevity\b", r"\blongevity differential\b", r"\bservice increment\b"],
    "overtime": [r"\bovertime\b", r"\bO\.?T\.?\b", r"\btime and one[- ]half\b", r"\bcompensatory time\b"],
    "holidays": [r"\bholiday(s)?\b", r"\bobserved holiday\b"],
    "vacation": [r"\bvacation\b", r"\bannual leave\b"],
    "sick-leave": [r"\bsick (leave|day|time|pay)\b", r"\bsick bank\b"],
    "parental-leave": [r"\bparental leave\b", r"\bmaternity\b", r"\bpaternity\b", r"\bchild[-\s]?bonding\b", r"\bfamily leave\b"],
    "other-leave": [r"\bjury duty\b", r"\bbereavement\b", r"\bmilitary leave\b", r"\bunpaid leave\b"],
    "health-welfare": [r"\bhealth\s+(insurance|benefits|plan)\b", r"\bwelfare fund\b", r"\bhealth and welfare\b", r"\bmedical benefits\b"],
    "pension": [r"\bpension\b", r"\bretirement\b", r"\bNYCERS\b", r"\bTRS\b", r"\bdeferred compensation\b"],
    "grievance": [r"\bgrievance\b", r"\barbitration\b", r"\bstep [1-4]\b"],
    "discipline": [r"\bdiscipline\b", r"\bdisciplinar(y|y action)\b", r"\btermination\b", r"\bdischarg(e|ed)\b", r"\bjust cause\b", r"\bsection 75\b", r"\bcounseling memo(randum)?\b"],
    "layoff": [r"\blayoff\b", r"\breduction in force\b", r"\bRIF\b", r"\bbump(ing)?\b", r"\bseniority\b"],
    "hours": [r"\bwork(ing)? hours\b", r"\bwork day\b", r"\bwork week\b", r"\bschedul(e|ing)\b", r"\btour\b", r"\bshift\b"],
    "shift-differential": [r"\bshift differential\b", r"\bnight (shift )?differential\b"],
    "uniform-allowance": [r"\buniform allowance\b", r"\buniform maintenance\b", r"\bequipment allowance\b"],
    "training": [r"\btraining\b", r"\beducation reimbursement\b", r"\btuition\b"],
    "safety": [r"\bsafety\b", r"\bhealth and safety\b", r"\bunsafe\b", r"\binjur(y|ies)\b", r"\bworkers'? compensation\b"],
    "no-strike": [r"\bno[- ]strike\b", r"\bstrike\b", r"\bwork stoppage\b"],
    "management-rights": [r"\bmanagement (rights|prerogatives?)\b"],
    "work-rules": [r"\bwork rules?\b", r"\bpersonnel rules\b"],
    "agency-shop": [r"\bagency (fee|shop)\b", r"\bdues check[- ]?off\b", r"\bdues deduction\b", r"\bunion (membership|security)\b"],
    "recognition": [r"\brecognition\b", r"\bbargaining unit\b", r"\bcertif(y|ication|ied) representative\b"],
    "promotion": [r"\bpromotion\b", r"\bcivil service\b", r"\beligible list\b"],
    "telework": [r"\btelework\b", r"\bremote work\b", r"\btelecommut\b", r"\bflexible work\b"],
    "diversity": [r"\bdiscrimination\b", r"\bharassment\b", r"\bequal (employment )?opportunity\b", r"\bDEI\b"],
    "workforce-comp": [r"\bworkforce composition\b", r"\bcomp(osition|liance) of (the )?workforce\b"],
}

COMPILED = {topic: [re.compile(p, re.IGNORECASE) for p in pats] for topic, pats in TOPICS.items()}


def topics_for(text: str, heading: str = ""):
    blob = (heading + "\n" + text)[:5000]  # cap for speed
    hits = []
    for topic, patterns in COMPILED.items():
        for rx in patterns:
            if rx.search(blob):
                hits.append(topic)
                break
    return hits


def main():
    clauses = json.loads((DATA / "clauses.json").read_text())
    counts = {t: 0 for t in TOPICS}
    for c in clauses:
        tags = topics_for(c.get("text", ""), c.get("heading", ""))
        c["topics"] = tags
        for t in tags:
            counts[t] += 1
    (DATA / "clauses.json").write_text(json.dumps(clauses, indent=1))
    print(f"Tagged {len(clauses)} clauses")
    for t, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {n:5d}  {t}")


if __name__ == "__main__":
    main()
