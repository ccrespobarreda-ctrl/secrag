#!/usr/bin/env python3
"""
Parse 10-K HTML into sections.

    python src/parse.py --raw data/raw --out data/parsed

This is the ugly part of the project, and the ugliness is worth naming because
each defect below cost a real debugging session and the fix is not obvious.

FOUR TRAPS IN EDGAR HTML

1. The table of contents repeats every Item heading before the sections
   themselves. A naive regex for "Item 1A" finds the TOC entry, and the extracted
   "section" turns out to be two lines of a contents table. Handled by requiring a
   heading to be followed by a minimum amount of prose to count.

2. Heading format is inconsistent within a single filing, let alone across
   companies. Observed in the wild:
       ITEM 1.   BUSINESS
       Item 1A. Risk Factors
       Item&nbsp;3.  Legal Proceedings
       Item 7. Management's Discussion and Analysis
   Handled by normalizing whitespace and entities before matching, and by a
   pattern tolerant of the period, the spacing and the case.

3. Financial tables are laid out with nested <div> rather than <table>, so
   get_text() runs the numbers together into an unreadable stream. Handled by
   inserting separators at block-level boundaries before extracting text.

4. Apostrophes arrive as &#8217; (right single quotation mark), not '. A pattern
   written with a plain apostrophe silently never matches "Management's".

WHAT THIS DELIBERATELY DOES NOT DO

It does not try to parse the financial tables into structured numbers. That is a
different project. The numbers stay in the text where the retriever can find
them, and the model reads them in context.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
import warnings
from pathlib import Path

from bs4 import BeautifulSoup

# Many filings are XHTML with inline XBRL. lxml parses them correctly in HTML
# mode; the warning is noise, not a signal, and it drowns the MISSING lines that
# do matter.
try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("parse")

# Only filters matches with essentially no body. It is NOT the mechanism that
# discards table-of-contents entries — a fixed threshold conflates "short because
# it is a contents line" with "short because the section is genuinely brief", and
# Item 3 (Legal Proceedings) is often two sentences. Verified: a 400-char
# threshold silently dropped a real Item 1 of 392 chars.
MIN_SECTION_CHARS = 80

# Block-level tags whose boundaries must survive as whitespace, or a div-laid-out
# table collapses into "Revenue51,217Cost of sales28,925".
BLOCK_TAGS = ["p", "div", "br", "tr", "td", "th", "li", "h1", "h2", "h3", "h4"]

# ─────────────────────────────────────────────────────────────────────
# The Item 8 cross-reference
# ─────────────────────────────────────────────────────────────────────
# Some filers put the financial statements inside Item 8. Others put a pointer
# there and place the statements in the F-pages after the Item sections:
#
#   "The consolidated financial statements and supplementary data are as set
#    forth in the index to consolidated financial statements on page F-1."
#
# Observed in 3 of 18 filings. The parser was right to capture what Item 8 says;
# the problem is that for those companies the corpus would then contain no
# financial statements at all, and every revenue question about them would fail
# with no indication why.
#
# Detected by size — a real Item 8 runs to six figures of characters — and
# recovered by finding the statements where they actually live.
CROSSREF_MAX_CHARS = 3_000

# The F-pages open with one of these. The auditor's report is required by PCAOB
# standards and is the most reliable marker.
FPAGE_ANCHORS = [
    "report of independent registered public accounting firm",
    "consolidated balance sheet",
    "consolidated statements of operations",
    "consolidated statements of income",
    "consolidated statement of operations",
]

# Below this the recovery found a heading rather than the statements.
MIN_FPAGE_CHARS = 5_000


def normalize_text(text: str) -> str:
    """
    Collapse the whitespace zoo EDGAR emits.

    NFKC folds non-breaking spaces and typographic quotes into their plain
    equivalents, which is what makes a pattern written with a normal apostrophe
    match "Management&#8217;s" after unescaping.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")   # zero-width
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "head"]):
        tag.decompose()

    # Separators at block boundaries, before extraction. Without this, tables
    # built from divs come out as one unbroken string of digits.
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")

    return normalize_text(soup.get_text())


# "Item 1A." / "ITEM 1A" / "Item 1A -" at the start of a line, tolerant of the
# period, the dash and the spacing that varies between filings.
_ITEM_PATTERN = re.compile(
    r"^\s*item\s+(\d{1,2}[A-C]?)\s*[.\-–—:]?\s*(.{0,90})$",
    re.IGNORECASE | re.MULTILINE,
)


def find_sections(text: str) -> list[dict]:
    """
    Locate Item sections, discarding table-of-contents matches.

    Every heading match is a candidate, and the same Item usually matches twice:
    once in the table of contents and once at the real section. Rather than trying
    to detect the TOC — a heuristic that breaks on the first filing that formats it
    differently — the rule is simply to keep the longest body found for each Item.

    A contents line yields tens of characters; the section it points at yields
    thousands. Length decides, and it decides correctly even when the real section
    is short, because the contents line is always shorter still.
    """
    candidates = []
    for m in _ITEM_PATTERN.finditer(text):
        item = f"Item {m.group(1).upper()}"
        if item not in C.ITEM_SECTIONS:
            continue
        candidates.append({
            "item": item,
            "title": C.ITEM_SECTIONS[item],
            "heading_text": m.group(0).strip()[:90],
            "start": m.end(),
        })

    sections = []
    for i, cand in enumerate(candidates):
        end = candidates[i + 1]["start"] if i + 1 < len(candidates) else len(text)
        body = text[cand["start"]:end].strip()

        if len(body) < MIN_SECTION_CHARS:
            log.debug("  skipped %s at offset %d (%d chars — table of contents)",
                      cand["item"], cand["start"], len(body))
            continue

        sections.append({
            "item_section": cand["item"],
            "section_title": cand["title"],
            "heading_as_found": cand["heading_text"],
            "content": body,
            "char_count": len(body),
            # Kept so the F-page recovery can search after this point rather
            # than matching the same phrases in the table of contents.
            "start": cand["start"],
        })

    # A filing can repeat a section; keep the longest occurrence of each.
    best: dict[str, dict] = {}
    for s in sections:
        prev = best.get(s["item_section"])
        if prev is None or s["char_count"] > prev["char_count"]:
            best[s["item_section"]] = s

    return sorted(best.values(), key=lambda s: s["item_section"])


def recover_fpages(text: str, item8_start: int) -> tuple[int, str] | None:
    """
    Find the financial statements when Item 8 only points at them.

    Searches after the Item 8 heading so table-of-contents mentions of the same
    phrases cannot match, and takes the earliest anchor found — the auditor's
    report precedes the statements, which precede the notes, so the earliest
    anchor yields the most complete capture.

    Runs to the end of the document. The F-pages are the last substantive content
    in a 10-K; what follows is signature blocks and exhibit boilerplate.
    """
    lowered = text.lower()
    positions = []
    for anchor in FPAGE_ANCHORS:
        pos = lowered.find(anchor, item8_start)
        if pos != -1:
            positions.append((pos, anchor))

    if not positions:
        return None

    start, anchor = min(positions)
    body = text[start:].strip()
    if len(body) < MIN_FPAGE_CHARS:
        return None
    return start, body


def parse_filing(path: Path) -> dict:
    html = path.read_text(encoding="utf-8", errors="ignore")
    text = html_to_text(html)
    sections = find_sections(text)

    recovered = False
    for s in sections:
        if s["item_section"] != "Item 8" or s["char_count"] > CROSSREF_MAX_CHARS:
            continue
        found = recover_fpages(text, s.get("start", 0))
        if not found:
            log.warning("  %s: Item 8 is %d chars and the F-pages were not found",
                        path.stem, s["char_count"])
            continue
        _, body = found
        log.info("  %s: Item 8 was a cross-reference (%d chars); recovered "
                 "%d chars from the F-pages", path.stem, s["char_count"], len(body))
        s["content"] = body
        s["char_count"] = len(body)
        s["recovered_from_fpages"] = True
        recovered = True

    indexed = [s for s in sections if s["item_section"] in C.SECTIONS_TO_INDEX]

    return {
        "source_file": path.name,
        "total_chars": len(text),
        "sections_found": [s["item_section"] for s in sections],
        "sections_indexed": [s["item_section"] for s in indexed],
        "item8_recovered_from_fpages": recovered,
        "sections": indexed,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse 10-K HTML into sections")
    ap.add_argument("--raw", default=C.RAW_DIR, type=Path)
    ap.add_argument("--out", default=C.PARSED_DIR, type=Path)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    files = sorted(args.raw.glob("*.html"))
    if not files:
        log.error("No HTML in %s — run src/edgar.py first", args.raw)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    incomplete = []

    for path in files:
        parsed = parse_filing(path)
        dest = args.out / f"{path.stem}.json"
        dest.write_text(json.dumps(parsed, indent=1), encoding="utf-8")

        missing = set(C.SECTIONS_TO_INDEX) - set(parsed["sections_indexed"])
        flag = "" if not missing else f"  MISSING {','.join(sorted(missing))}"
        log.info("  %-28s %7d chars  %d sections%s",
                 path.stem, parsed["total_chars"], len(parsed["sections"]), flag)
        if missing:
            incomplete.append((path.stem, sorted(missing)))

    log.info("Parsed %d filings -> %s", len(files), args.out)

    if incomplete:
        # Not fatal. Some companies genuinely omit sections, and some format
        # headings in a way the pattern misses. Either way it needs a human eye
        # rather than a silent pass.
        log.warning("%d filings missing expected sections:", len(incomplete))
        for name, missing in incomplete:
            log.warning("    %-28s %s", name, ", ".join(missing))
        log.warning("Inspect one by hand before trusting the corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
