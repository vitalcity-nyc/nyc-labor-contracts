#!/usr/bin/env python3
"""
Edit-distance-2 OCR error detector using rapidfuzz against a corpus-derived
wordlist. Catches multi-character mangles like 'Drpuly → Deputy', 'Commssioner
→ Commissioner', 'Cortandt → Cortlandt' that the single-rule scanners miss.

Outputs data/ocr-suspects-fuzzy.json. Designed to be conservative: only flag
a candidate when there is a clear single best match within distance 2 (and
distance 1 ahead of any distance-2 alternatives).
"""
import json
import re
import string
from pathlib import Path
from collections import Counter, defaultdict

from rapidfuzz import process, fuzz, distance

ROOT = Path(__file__).resolve().parent.parent
CLAUSES = ROOT / "data" / "clauses.json"
DICT_PATH = Path("/usr/share/dict/words")
OUT = ROOT / "data" / "ocr-suspects-fuzzy.json"

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]{2,}")


def load_dict():
    """Two wordlists:
       - is_word_dict (broad): BSD ∪ multi-contract corpus words ∪ extras.
         Used to decide whether a token is already a real word (don't flag).
       - candidate_dict (narrow): BSD ∩ multi-contract corpus words ∪ extras.
         Used as the SPACE rapidfuzz searches for replacements — keeps
         archaic BSD words out of suggestions while ensuring suggestions
         are real English."""
    bsd = set()
    with DICT_PATH.open() as f:
        for line in f:
            bsd.add(line.strip().lower())
    clauses = json.loads(CLAUSES.read_text())
    contracts_per_word = defaultdict(set)
    total_count = Counter()
    for c in clauses:
        cid = c["contract_id"]
        for m in WORD_RE.finditer(c.get("text", "") or ""):
            w = m.group(0).lower().strip("'-")
            if w:
                contracts_per_word[w].add(cid)
                total_count[w] += 1
    # Multi-contract: word appears in >= 3 distinct contracts AND appears >= 5x total
    multi = {w for w, cs in contracts_per_word.items()
             if len(cs) >= 3 and total_count[w] >= 5}
    EXTRAS = {
        # Core function/grammatical words that may be missing if a contract has
        # few non-OCR pages
        "the","and","of","to","in","for","with","on","at","by","an","or","be",
        "is","are","was","were","been","has","have","had","not","no","yes",
        "shall","may","will","would","should","could","must","can",
        "this","that","these","those","such","any","all","each","every",
        "from","about","between","through","under","over","into","upon",
        "where","when","why","who","whom","which","what","whose",
        "until","unless","whether","because","while","during","after","before",
        # NYC labor-contract domain words
        "employer","employee","employees","employers",
        "arbitrator","arbitration","grievance","grievant","grievances",
        "memorandum","memoranda","agreement","agreements",
        "bargaining","negotiated","negotiations","predecessor","successor",
        "longevity","differential","differentials","pensionable",
        "uniformed","subcontract","subcontracted","subcontracting",
        "noncompliance","nondiscrimination","reclassification","reclassified",
        "comptroller","commissioner","council","union","unions","local",
        "department","city","new","york","manhattan","brooklyn","queens","bronx",
        # Common English missing from BSD for various reasons
        "categories","category","technologies","technology","specifies",
        "specified","based","heard","held","categorized","retiree","retirees",
        "hereto","hereof","herein","hereinafter","hereinabove","heretofore",
        "thereof","thereto","thereafter","therein","thereon","thereunder",
        "whereof","whereto","whereas","wherein",
        "agrees","agreed","agreement","agreements","agreeable","agreeing",
        "rate","rates","wage","wages","salary","salaries",
        "overtime","compensation","compensable","compensatory",
        "vehicles","operating","operational","operation","operations",
        "international","national","association","federation",
        "deputy","director","directors","officer","officers","commissioner",
        "deputies","first","second","third","fourth","fifth","sixth","seventh",
        "labor","relations","strategy","health","care","program","programs",
        "benefit","benefits","insurance","pension","welfare","fund","funds",
    }
    is_word_dict = (bsd | multi | EXTRAS)
    candidate_dict = ((bsd & multi) | EXTRAS)
    is_word_dict = {w for w in is_word_dict if len(w) >= 4}
    candidate_dict = {w for w in candidate_dict if len(w) >= 4}
    return is_word_dict, candidate_dict, clauses


def is_word(token, words):
    t = token.lower().strip("'’-")
    if not t:
        return False
    if t in words:
        return True
    for suf, repl in [("s", ""), ("es", ""), ("ed", ""), ("ed", "e"),
                      ("ing", ""), ("ing", "e"), ("ly", ""),
                      ("ies", "y"), ("'s", "")]:
        if t.endswith(suf):
            stem = t[:-len(suf)] + repl
            if stem in words:
                return True
    return False


def find_best(token, choices_list):
    """Find the best match for token within edit distance 2.
    Returns (candidate, distance, second_distance) or None."""
    # Prefer rapidfuzz extract with Levenshtein distance
    matches = process.extract(
        token.lower(),
        choices_list,
        scorer=distance.Levenshtein.distance,
        limit=3,
        score_cutoff=2,  # max distance 2
    )
    if not matches:
        return None
    # matches: [(candidate, score=distance, idx), ...]
    best_cand, best_dist, _ = matches[0]
    second_dist = matches[1][1] if len(matches) > 1 else 99
    return best_cand, best_dist, second_dist


def context_around(text, start, end, pad=70):
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    s = text[a:b].replace("\n", " ")
    if a > 0: s = "…" + s
    if b < len(text): s = s + "…"
    return s


def main():
    print("Loading wordlist & clauses…")
    is_words, cand_words, clauses = load_dict()
    word_list = sorted(cand_words)
    print(f"  is_word dict: {len(is_words):,}, candidate dict: {len(cand_words):,}; {len(clauses):,} clauses")

    print("Scanning OCR'd clauses…")
    suspects = []
    seen_pairs = set()
    skipped_short = 0
    skipped_known = 0

    # Limit per-token tries with a cache
    cache = {}

    for idx, clause in enumerate(clauses):
        if not clause.get("ocr"):
            continue
        text = clause.get("text") or ""
        for m in WORD_RE.finditer(text):
            token = m.group(0)
            if any(c.isdigit() for c in token):
                continue
            if len(token) < 5:
                skipped_short += 1
                continue
            if token.isupper():
                continue  # likely abbreviation/heading
            if is_word(token, is_words):
                skipped_known += 1
                continue
            key = (clause["contract_id"], token)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)

            tlow = token.lower()
            if tlow not in cache:
                cache[tlow] = find_best(token, word_list)
            best = cache[tlow]
            if not best:
                continue
            cand, dist, second_dist = best
            # Be conservative:
            #  - must be within distance 2
            #  - must be at least 1 closer than the next-best match (clear winner)
            #  - OR distance 1 (always trust)
            if dist == 0:
                continue  # shouldn't happen since is_word would have caught it
            if dist > second_dist - 1 and dist > 1:
                continue  # ambiguous tie at distance 2
            # Skip if candidate differs only by case (caught earlier)
            if cand.lower() == tlow:
                continue
            # Skip if candidate is just a different inflection (s/ed/ing) — those
            # would be word-form variants, not OCR errors
            if dist == 1 and (
                cand.lower() == tlow + "s" or cand.lower() + "s" == tlow or
                cand.lower() == tlow + "d" or cand.lower() + "d" == tlow
            ):
                continue
            # Match casing: capitalize candidate if original was capitalized
            if token[0].isupper():
                cand_cased = cand[0].upper() + cand[1:]
            else:
                cand_cased = cand
            suspects.append({
                "contract_id": clause["contract_id"],
                "clause_id": clause["id"],
                "page": clause.get("page"),
                "original": token,
                "candidate": cand_cased,
                "distance": dist,
                "next_distance": second_dist if second_dist < 99 else None,
                "context": context_around(text, m.start(), m.end()),
            })

    counts = Counter(s["original"] for s in suspects)
    suspects.sort(key=lambda s: (-counts[s["original"]], s["distance"], s["original"]))
    OUT.write_text(json.dumps({
        "total": len(suspects),
        "unique": len(counts),
        "top": counts.most_common(30),
        "suspects": suspects,
    }, indent=2, ensure_ascii=False))
    print(f"Wrote {len(suspects)} suspects ({len(counts)} unique tokens) → {OUT.name}")
    print("Top tokens:")
    for tok, n in counts.most_common(30):
        sug = next(s["candidate"] for s in suspects if s["original"] == tok)
        d = next(s["distance"] for s in suspects if s["original"] == tok)
        print(f"  {n:3d}× {tok:18} → {sug:18} (d={d})")


if __name__ == "__main__":
    main()
