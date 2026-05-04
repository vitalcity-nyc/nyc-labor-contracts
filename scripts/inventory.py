"""Build inventory of NYC municipal labor contracts from OLR pages.

Output: data/contracts.json with one entry per agreement.
"""
from __future__ import annotations
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

SOURCES = [
    # Only the Recent Agreements page — OLR's authoritative list of currently in-force
    # contracts (including ones with expired stated terms that remain operative under
    # New York State's Triborough Amendment until a successor is signed).
    ("recent", "https://www.nyc.gov/site/olr/labor/labor-recent-agreements.page"),
]

UA = {"User-Agent": "Mozilla/5.0 (compatible; nyc-labor-contracts/0.1; +https://github.com/joshgreenman1973/nyc-labor-contracts)"}


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:80]


YEAR_RE = re.compile(r"(\d{4})\s*[-–]\s*(\d{4})")


def parse_term(label: str):
    m = YEAR_RE.search(label)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def fetch(url: str) -> str:
    cache = DATA / f"_cache_{slugify(url)}.html"
    if cache.exists():
        return cache.read_text()
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    cache.write_text(r.text)
    return r.text


def collect(source_name: str, url: str):
    soup = BeautifulSoup(fetch(url), "lxml")
    items = []
    seen_hrefs = set()
    # Walk the page top-to-bottom, tracking the most recent heading as the section.
    section = None
    body = soup.find("body") or soup
    for el in body.descendants:
        if getattr(el, "name", None) in {"h1", "h2", "h3", "h4", "strong"}:
            txt = el.get_text(" ", strip=True)
            if txt and len(txt) < 120:
                # Heuristic: section heads tend to be short and contain words like Citywide, Uniformed, etc.
                if re.search(r"agreement|citywide|uniformed|education|economic|coalition|trade|skilled|welfare|board", txt, re.I):
                    section = txt
        if getattr(el, "name", None) == "a" and el.get("href"):
            href = el["href"]
            if not href.lower().endswith(".pdf"):
                continue
            if "collectivebargaining" not in href.lower() and "olr" not in href.lower():
                continue
            full = urljoin(url, href)
            if full in seen_hrefs:
                continue
            seen_hrefs.add(full)
            label = el.get_text(" ", strip=True)
            if not label:
                # use filename
                label = href.rsplit("/", 1)[-1].replace(".pdf", "").replace("-", " ").title()
            term_start, term_end = parse_term(label)
            items.append({
                "source": source_name,
                "section": section,
                "label": label,
                "url": full,
                "term_start": term_start,
                "term_end": term_end,
            })
    return items


def main():
    all_items = []
    for name, url in SOURCES:
        all_items.extend(collect(name, url))

    # Deduplicate by url, preferring the "recent" source.
    by_url = {}
    for it in all_items:
        if it["url"] in by_url and by_url[it["url"]]["source"] == "recent":
            continue
        by_url[it["url"]] = it

    contracts = []
    for it in by_url.values():
        cid = slugify(it["label"]) or slugify(it["url"].rsplit("/", 1)[-1])
        contracts.append({
            "id": cid,
            "label": it["label"],
            "section": it["section"],
            "source": it["source"],
            "url": it["url"],
            "term_start": it["term_start"],
            "term_end": it["term_end"],
        })

    # Resolve duplicate ids by appending a counter (track by ORIGINAL id, not rewritten)
    counts = {}
    for c in contracts:
        counts[c["id"]] = counts.get(c["id"], 0) + 1
    seen = {}
    for c in contracts:
        original = c["id"]
        if counts[original] > 1:
            n = seen.get(original, 0) + 1
            seen[original] = n
            c["id"] = f"{original}-{n}"

    out = DATA / "contracts.json"
    out.write_text(json.dumps(contracts, indent=2))
    print(f"Wrote {len(contracts)} contracts to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
