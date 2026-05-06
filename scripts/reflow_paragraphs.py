#!/usr/bin/env python3
"""
Reflow OCR-derived hard line breaks into proper paragraphs.

OCR PDFs preserve a hard newline at every visual line, which fragments prose.
This script joins consecutive lines within a paragraph (single newlines → space,
with de-hyphenation) while preserving structural breaks: blank lines, headings,
list items, blockquotes, tables, code fences, HTML blocks, frontmatter.
"""
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_DIR = ROOT / "data" / "markdown"
CLAUSES = ROOT / "data" / "clauses.json"

# Lines that are themselves block-structural — never merge them with neighbors.
STRUCTURAL = re.compile(
    r"^\s*("
    r"#{1,6}\s"               # headings
    r"|[-*+]\s"               # unordered list
    r"|\d+[.)]\s"             # ordered list
    r"|>"                     # blockquote
    r"|\|"                    # table
    r"|```"                   # code fence
    r"|<[a-zA-Z!/]"           # HTML/comments
    r"|---\s*$"               # rule
    r"|_Page \d+"             # our page-meta line
    r")"
)


def is_structural(line):
    return bool(STRUCTURAL.match(line))


SENTENCE_END = re.compile(r"[.!?\"'’)]\s*$")
LABEL_END = re.compile(r":\s*$")


def should_merge(prev, curr):
    """Merge curr into prev only if prev looks like a wrapped prose line."""
    if not prev or not curr:
        return False
    if prev.endswith("-"):
        return True  # de-hyphenation case, handled by caller
    if len(prev) < 30:
        return False  # short → likely a label, table cell, or terminator
    if SENTENCE_END.search(prev):
        return False  # sentence ended
    if LABEL_END.search(prev):
        return False  # label introducing a value
    if curr[:1].isdigit() and len(curr) < 40:
        return False  # likely a list/numeric continuation, keep separate
    if LABEL_END.search(curr):
        return False  # curr is itself a label like "TERM:" — don't absorb it
    return True


def reflow_paragraph(lines):
    """Join lines into one paragraph using conservative merge rules."""
    if not lines:
        return ""
    out = [lines[0].rstrip()]
    for raw in lines[1:]:
        ln = raw.rstrip()
        if not ln:
            continue
        prev = out[-1]
        if prev.endswith("-") and ln and ln[0].islower():
            out[-1] = prev[:-1] + ln
        elif should_merge(prev, ln):
            out[-1] = prev + " " + ln
        else:
            out.append(ln)
    return "\n".join(out)


def reflow_text(text, fence_safe=True):
    """Reflow a block of markdown text. Frontmatter and code fences pass through."""
    lines = text.splitlines()
    output = []
    paragraph = []
    in_fence = False
    in_frontmatter = False

    for i, raw in enumerate(lines):
        # Frontmatter passthrough
        if i == 0 and raw.strip() == "---":
            in_frontmatter = True
            output.append(raw)
            continue
        if in_frontmatter:
            output.append(raw)
            if raw.strip() == "---":
                in_frontmatter = False
            continue
        # Code fence passthrough
        if raw.lstrip().startswith("```"):
            if paragraph:
                output.append(reflow_paragraph(paragraph))
                paragraph = []
            output.append(raw)
            in_fence = not in_fence
            continue
        if in_fence:
            output.append(raw)
            continue
        # Blank line ends the current paragraph
        if not raw.strip():
            if paragraph:
                output.append(reflow_paragraph(paragraph))
                paragraph = []
            output.append("")
            continue
        # Structural lines flush, pass through, don't accumulate
        if is_structural(raw):
            if paragraph:
                output.append(reflow_paragraph(paragraph))
                paragraph = []
            output.append(raw)
            continue
        paragraph.append(raw)
    if paragraph:
        output.append(reflow_paragraph(paragraph))
    # Collapse trailing empties
    while output and not output[-1].strip():
        output.pop()
    return "\n".join(output) + "\n"


def reflow_clause_text(text):
    """Same logic, but for raw plain-text clauses (no markdown structure)."""
    paras = re.split(r"\n\s*\n", text)
    out = []
    for p in paras:
        lines = [ln.rstrip() for ln in p.splitlines() if ln.strip()]
        if not lines:
            continue
        # Don't reflow if it looks like tabular / list-y data: lots of short
        # lines, or many lines starting with digits/dollar signs/dashes
        short = sum(1 for ln in lines if len(ln) < 40)
        tabular = sum(1 for ln in lines if re.match(r"^[\d$.,\-•*\s]+$", ln))
        if len(lines) >= 3 and (short > len(lines) * 0.6 or tabular > len(lines) * 0.4):
            out.append("\n".join(lines))
            continue
        joined = [lines[0]]
        for ln in lines[1:]:
            prev = joined[-1]
            if prev.endswith("-") and ln and ln[0].islower():
                joined[-1] = prev[:-1] + ln
            elif should_merge(prev, ln):
                joined[-1] = prev + " " + ln
            else:
                joined.append(ln)
        out.append("\n".join(joined))
    return "\n\n".join(out)


def main():
    # Markdown
    md_count = 0
    for path in sorted(MD_DIR.glob("*.md")):
        original = path.read_text()
        new = reflow_text(original)
        if new != original:
            path.write_text(new)
            md_count += 1
    print(f"Reflowed {md_count} markdown files")

    # clauses.json — reflow each clause text
    clauses = json.loads(CLAUSES.read_text())
    changed = 0
    for c in clauses:
        if not c.get("text"):
            continue
        new_text = reflow_clause_text(c["text"])
        if new_text != c["text"]:
            c["text"] = new_text
            changed += 1
    CLAUSES.write_text(json.dumps(clauses, indent=1, ensure_ascii=False) + "\n")
    print(f"Reflowed {changed}/{len(clauses)} clauses in clauses.json")


if __name__ == "__main__":
    main()
