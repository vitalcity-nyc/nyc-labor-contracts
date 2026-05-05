#!/usr/bin/env python3
"""
Surface candidate OCR errors without auto-fixing them.

Strategy: only flag a token when (a) it is NOT a real word and (b) applying a
single known OCR misread substitution turns it into a real word. That gives a
high-precision, easy-to-review list — anything ambiguous is left alone.

Output: data/ocr-suspects.json — fed to ocr-review.html for human review.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUSES = ROOT / "data" / "clauses.json"
OUT = ROOT / "data" / "ocr-suspects.json"
DICT_PATH = Path("/usr/share/dict/words")

# Known macOS Vision OCR misreads, restricted to the high-precision ones.
# Things like l↔I and l↔1 generate too much garbage; left out on purpose.
SUBSTITUTIONS = [
    ("v", "y"),     # Pavment → Payment, salarv → salary, Emplovee → Employee
    ("rn", "m"),    # bum vs burn (avoided by dictionary check on candidate)
    ("m", "rn"),    # govemment → government
    ("cl", "d"),
    ("d", "cl"),
    ("c", "e"),     # carning → earning, ct → et confusions
    ("e", "c"),
    ("n", "u"),     # rmgn vs rmgu — less common but real for some fonts
    ("u", "n"),
    ("h", "b"),     # hut vs but
    ("b", "h"),
    ("ii", "n"),    # ii read as n
    ("n", "ii"),
    ("li", "h"),    # li read as h, e.g. "Iiarry" → "harry"? rare
    ("h", "li"),
    ("ti", "ii"),
    ("ii", "ti"),
]

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]{2,}")  # 3+ letter tokens


def load_words():
    words = set()
    with DICT_PATH.open() as f:
        for line in f:
            words.add(line.strip().lower())
    # Add common contract-domain words missing from /usr/share/dict
    extras = {
        "arbitrator", "arbitration", "grievance", "grievant",
        "employer", "employee", "employees", "employers",
        "bargaining", "bargained", "negotiated", "negotiations",
        "predecessor", "successor",
        "memorandum", "memoranda",
        "bylaws", "subsection", "subsections", "subarticle",
        "healthcare", "workplace", "worksite", "worksites",
        "longevity", "differential", "differentials",
        "pensionable", "pensioner", "pensioners",
        "uniformed", "non-uniformed",
        "subcontract", "subcontracted", "subcontracting",
        "reclassification", "reclassified",
        "overtime", "comp", "compensatory",
        "preempt", "preemption",
        "noncompliance", "nondiscrimination",
        "chargeback", "chargebacks",
        # Common modern words missing from BSD dict
        "held", "heard", "based", "basing",
        "categories", "category", "technologies", "technology",
        "specifies", "specified", "specifying",
        "hereto", "hereof", "herein", "hereinafter", "hereinabove", "heretofore",
        "thereof", "thereto", "thereafter", "therein",
        "shall", "should", "would", "could",
        "until", "unless", "whether",
        "agrees", "agreed", "agreement", "agreements", "agreeable",
    }
    return words | extras


def is_word(token, words):
    t = token.lower().strip("'’-")
    if not t:
        return False
    if t in words:
        return True
    # Handle inflections missing from BSD wordlist
    if t.endswith("s") and t[:-1] in words:
        return True
    if t.endswith("es") and t[:-2] in words:
        return True
    if t.endswith("ed") and t[:-2] in words:
        return True
    if t.endswith("ed") and t[:-1] in words:  # used → use
        return True
    if t.endswith("ing") and t[:-3] in words:
        return True
    if t.endswith("ing") and (t[:-3] + "e") in words:  # using → use
        return True
    if t.endswith("ly") and t[:-2] in words:
        return True
    if t.endswith("'s") and t[:-2] in words:
        return True
    if t.endswith("ies") and (t[:-3] + "y") in words:
        return True
    return False


def looks_like_proper_noun(token):
    """All-caps tokens or capitalized single words alone are usually names."""
    if token.isupper():
        return True
    return False


def has_digits(token):
    return any(c.isdigit() for c in token)


def find_suggestions(token, words):
    """Return list of (suggested_token, substitution) where replacing one
    occurrence of an OCR-confused pattern turns this non-word into a real word."""
    if is_word(token, words):
        return []
    if looks_like_proper_noun(token):
        return []
    seen = set()
    suggestions = []
    lower = token.lower()
    for old, new in SUBSTITUTIONS:
        # Replace each occurrence individually
        start = 0
        while True:
            idx = lower.find(old, start)
            if idx == -1:
                break
            candidate = token[:idx] + new + token[idx + len(old):]
            start = idx + 1
            if candidate == token or candidate in seen:
                continue
            seen.add(candidate)
            if has_digits(new) and not has_digits(token):
                continue
            if is_word(candidate, words):
                suggestions.append({"candidate": candidate, "rule": f"{old}→{new}"})
    return suggestions


def context_around(text, start, end, pad=70):
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    snippet = text[a:b].replace("\n", " ")
    if a > 0:
        snippet = "…" + snippet
    if b < len(text):
        snippet = snippet + "…"
    return snippet


def main():
    words = load_words()
    clauses = json.loads(CLAUSES.read_text())
    print(f"Loaded {len(clauses)} clauses, {len(words)} dictionary words")

    suspects = []
    seen_pairs = set()  # (contract_id, original) — dedupe per contract

    for clause in clauses:
        if not clause.get("ocr"):
            continue
        text = clause.get("text") or ""
        for m in WORD_RE.finditer(text):
            token = m.group(0)
            if has_digits(token):
                continue
            if len(token) < 4:
                continue
            suggestions = find_suggestions(token, words)
            if not suggestions:
                continue
            key = (clause["contract_id"], token)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            suspects.append({
                "contract_id": clause["contract_id"],
                "clause_id": clause["id"],
                "page": clause.get("page"),
                "heading": clause.get("heading"),
                "original": token,
                "suggestions": suggestions,
                "context": context_around(text, m.start(), m.end()),
            })

    # Sort: most common originals first (likely real OCR error patterns)
    from collections import Counter
    counts = Counter(s["original"] for s in suspects)
    suspects.sort(key=lambda s: (-counts[s["original"]], s["original"], s["contract_id"]))

    OUT.write_text(json.dumps({
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total": len(suspects),
        "unique_originals": len(counts),
        "top_patterns": counts.most_common(20),
        "suspects": suspects,
    }, indent=2, ensure_ascii=False))
    print(f"Wrote {len(suspects)} suspects ({len(counts)} unique tokens) → {OUT}")
    print("Top 20 most-common suspect tokens:")
    for tok, n in counts.most_common(20):
        print(f"  {n:4d}  {tok}")


if __name__ == "__main__":
    main()
