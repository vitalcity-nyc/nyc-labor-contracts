# NYC municipal labor contracts

Searchable full-text database of every collective bargaining agreement currently in force for New York City municipal employees.

Source: NYC Office of Labor Relations Recent Agreements page. Many contracts are published only as scanned image PDFs whose text isn't selectable; this project OCRs every page so the full text of every agreement is searchable, taggable by topic, and quotable with a stable link to the source clause.

Live site: https://vitalcity-nyc.github.io/nyc-labor-contracts/

See [methodology.html](methodology.html) for sources, pipeline, and limitations.

## Reproduce

```
python3 -m venv .venv && source .venv/bin/activate
pip install pypdf pdfplumber requests beautifulsoup4 lxml pypdfium2 ocrmac
python scripts/inventory.py
python scripts/scrape.py
python scripts/extract.py
python scripts/segment.py
python scripts/tag.py
python scripts/build_manifest.py
python -m http.server 8000
```
