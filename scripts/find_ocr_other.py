#!/usr/bin/env python3
"""
Three more OCR-error detectors that the substitution scanner doesn't cover:

  --kind=drops      Letter drops/doubles (edit distance 1, e.g. anual → annual)
  --kind=fragments  Line-break fragments (e.g. in- cluding → including)
  --kind=spaces     Missing word boundaries (e.g. ofTcamsters → of Teamsters)

Each writes a separate suspect JSON for review:
  data/ocr-suspects-drops.json
  data/ocr-suspects-fragments.json
  data/ocr-suspects-spaces.json
"""
import argparse
import json
import re
import string
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUSES = ROOT / "data" / "clauses.json"
DICT_PATH = Path("/usr/share/dict/words")
ALPHABET = string.ascii_lowercase

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]{2,}")


def load_words():
    words = set()
    with DICT_PATH.open() as f:
        for line in f:
            words.add(line.strip().lower())
    extras = {
        "held", "heard", "based", "categories", "category",
        "technologies", "technology", "specifies",
        "hereto", "hereof", "herein", "hereinafter", "hereinabove",
        "heretofore", "thereof", "thereto", "thereafter", "therein",
        "shall", "until", "whether",
        "agrees", "agreed", "agreement", "agreements", "agreeable",
        "employer", "employee", "employees", "employers",
        "arbitrator", "arbitration", "grievance",
        "memorandum", "memoranda",
        "longevity", "differential", "differentials",
        "uniformed", "subcontract", "overtime",
        "preempt", "noncompliance", "nondiscrimination",
        "reappointed", "reappointment",
    }
    return words | extras


def is_word(token, words):
    t = token.lower().strip("'’-")
    if not t:
        return False
    if t in words:
        return True
    if t.endswith("s") and t[:-1] in words: return True
    if t.endswith("es") and t[:-2] in words: return True
    if t.endswith("ed") and t[:-2] in words: return True
    if t.endswith("ed") and t[:-1] in words: return True
    if t.endswith("ing") and t[:-3] in words: return True
    if t.endswith("ing") and (t[:-3] + "e") in words: return True
    if t.endswith("ly") and t[:-2] in words: return True
    if t.endswith("ies") and (t[:-3] + "y") in words: return True
    if t.endswith("'s") and t[:-2] in words: return True
    return False


def context_around(text, start, end, pad=70):
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    s = text[a:b].replace("\n", " ")
    if a > 0: s = "…" + s
    if b < len(text): s = s + "…"
    return s


# ----------------------------------------------------------------------
# Pass 1 — letter drop/double
# ----------------------------------------------------------------------
def edit_neighbors_drop_double(token):
    """Generate all edit-distance-1 neighbors via INSERT or DELETE only.
    These are the dominant OCR errors (anual -> annual; accrued -> accred)."""
    seen = set()
    lower = token.lower()
    # Inserts (add one char at each position) — fixes drops
    for i in range(len(lower) + 1):
        for c in ALPHABET:
            cand = lower[:i] + c + lower[i:]
            seen.add(cand)
    # Deletes (remove one char) — fixes doubles/extras
    for i in range(len(lower)):
        cand = lower[:i] + lower[i+1:]
        if cand:
            seen.add(cand)
    return seen


COMMON_INSERT_LETTERS = set("aeioulmnrstdh")  # most likely OCR drops


def find_drop_double(token, words):
    """Return list of high-confidence drop/double fixes."""
    if is_word(token, words):
        return []
    if token.isupper():
        return []
    suggestions = []
    seen = set()
    lower = token.lower()
    # Drops: insert one letter
    for i in range(len(lower) + 1):
        for c in ALPHABET:
            if c not in COMMON_INSERT_LETTERS:
                continue
            cand = lower[:i] + c + lower[i:]
            if cand == lower or cand in seen:
                continue
            seen.add(cand)
            if is_word(cand, words):
                # Capitalize fix to match original casing
                if token[0].isupper():
                    cand_cased = cand.capitalize()
                else:
                    cand_cased = cand
                suggestions.append({"candidate": cand_cased, "rule": f"insert '{c}' at {i}"})
    # Doubles: remove one letter
    for i in range(len(lower)):
        cand = lower[:i] + lower[i+1:]
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if is_word(cand, words):
            if token[0].isupper():
                cand_cased = cand.capitalize()
            else:
                cand_cased = cand
            suggestions.append({"candidate": cand_cased, "rule": f"drop char at {i}"})
    return suggestions


def scan_drops(clauses, words):
    suspects = []
    seen = set()
    for clause in clauses:
        if not clause.get("ocr"):
            continue
        text = clause.get("text") or ""
        for m in WORD_RE.finditer(text):
            token = m.group(0)
            if any(c.isdigit() for c in token):
                continue
            if len(token) < 5:  # short tokens too noisy
                continue
            sugs = find_drop_double(token, words)
            if not sugs:
                continue
            # Limit to one suggestion per token to reduce noise
            sugs = sugs[:3]
            key = (clause["contract_id"], token)
            if key in seen:
                continue
            seen.add(key)
            suspects.append({
                "kind": "drop-double",
                "contract_id": clause["contract_id"],
                "clause_id": clause["id"],
                "page": clause.get("page"),
                "original": token,
                "suggestions": sugs,
                "context": context_around(text, m.start(), m.end()),
            })
    return suspects


# ----------------------------------------------------------------------
# Pass 2 — line-break fragments
# ----------------------------------------------------------------------
TOKENIZER = re.compile(r"\b[A-Za-z][A-Za-z'’\-]*\b")


def scan_fragments(clauses, words):
    """Find adjacent tokens A, B where neither is a word, but A+B is."""
    suspects = []
    seen = set()
    for clause in clauses:
        if not clause.get("ocr"):
            continue
        text = clause.get("text") or ""
        toks = list(TOKENIZER.finditer(text))
        for i in range(len(toks) - 1):
            a_m = toks[i]
            b_m = toks[i + 1]
            a, b = a_m.group(0), b_m.group(0)
            if any(c.isdigit() for c in a + b):
                continue
            # Only consider when the gap between them is short whitespace (likely line break)
            gap = text[a_m.end():b_m.start()]
            if len(gap) > 4 or gap.strip("- \n\r\t"):
                continue
            joined = (a + b).replace("-", "")
            if len(a) < 2 or len(b) < 2:
                continue
            if is_word(a, words) and is_word(b, words):
                continue
            if is_word(joined, words):
                key = (clause["contract_id"], a, b)
                if key in seen:
                    continue
                seen.add(key)
                suspects.append({
                    "kind": "fragment",
                    "contract_id": clause["contract_id"],
                    "clause_id": clause["id"],
                    "page": clause.get("page"),
                    "original": f"{a} {b}",
                    "suggestions": [{"candidate": joined, "rule": "rejoin"}],
                    "context": context_around(text, a_m.start(), b_m.end()),
                })
    return suspects


# ----------------------------------------------------------------------
# Pass 3 — missing word boundary (lowercase→uppercase transition mid-token)
# ----------------------------------------------------------------------
CAMEL_RE = re.compile(r"([a-z]{2,})([A-Z][a-z]{2,})")


def scan_missing_spaces(clauses, words):
    suspects = []
    seen = set()
    for clause in clauses:
        if not clause.get("ocr"):
            continue
        text = clause.get("text") or ""
        for m in WORD_RE.finditer(text):
            token = m.group(0)
            cm = CAMEL_RE.search(token)
            if not cm:
                continue
            a, b = cm.group(1), cm.group(2)
            if not (is_word(a, words) and is_word(b, words)):
                continue
            # Skip if the whole token is itself a known word (CamelCase brand)
            if is_word(token, words):
                continue
            key = (clause["contract_id"], token)
            if key in seen:
                continue
            seen.add(key)
            split = token[:cm.start(2)] + " " + token[cm.start(2):]
            suspects.append({
                "kind": "missing-space",
                "contract_id": clause["contract_id"],
                "clause_id": clause["id"],
                "page": clause.get("page"),
                "original": token,
                "suggestions": [{"candidate": split, "rule": "split"}],
                "context": context_around(text, m.start(), m.end()),
            })
    return suspects


# ----------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kind", required=True, choices=["drops", "fragments", "spaces"])
    args = p.parse_args()

    words = load_words()
    clauses = json.loads(CLAUSES.read_text())
    print(f"Loaded {len(clauses)} clauses")

    if args.kind == "drops":
        suspects = scan_drops(clauses, words)
        out = ROOT / "data" / "ocr-suspects-drops.json"
    elif args.kind == "fragments":
        suspects = scan_fragments(clauses, words)
        out = ROOT / "data" / "ocr-suspects-fragments.json"
    elif args.kind == "spaces":
        suspects = scan_missing_spaces(clauses, words)
        out = ROOT / "data" / "ocr-suspects-spaces.json"

    counts = Counter(s["original"] for s in suspects)
    suspects.sort(key=lambda s: (-counts[s["original"]], s["original"]))
    out.write_text(json.dumps({
        "kind": args.kind,
        "total": len(suspects),
        "unique": len(counts),
        "top": counts.most_common(20),
        "suspects": suspects,
    }, indent=2, ensure_ascii=False))
    print(f"Wrote {len(suspects)} suspects ({len(counts)} unique) → {out.name}")
    print(f"Top:")
    for tok, n in counts.most_common(20):
        print(f"  {n:3d}  {tok}")


if __name__ == "__main__":
    main()
