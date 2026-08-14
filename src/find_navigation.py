#!/usr/bin/env python3
"""
Measure how much of the corpus is navigation rather than content.

    python src/find_navigation.py
    python src/find_navigation.py --threshold 0.5 --show 10

A chunk was observed outranking the correct answer for a revenue question:

    INDEX Note 1 Description of Business and Basis of Presentation 55
    Note 2 Summary of Significant Accounting Policies 55 Note 3 Property...

That is a table of contents. It scores well on both retrieval paths for the same
reason it is useless: it names many topics densely and develops none of them.

Filtering it is tempting. The question is how much of the corpus this is, and
whether a rule that removes it also removes real content — financial statements
are legitimately dense in numbers with few full sentences, and a careless filter
would delete exactly the passages the corpus exists for.

So this measures first. It flags nothing on its own.

RESULT ON THE REAL CORPUS: DO NOT FILTER

Run against 4,169 chunks, the score was measured and the filter was rejected.
Two findings, and the second is the reason:

  1. The problem is negligible. Eleven chunks score above 0.5 — 0.3% of the
     corpus, 0.7% of Item 8, and none anywhere else. The index chunk that
     outranked a correct answer in one manual search is an isolated case rather
     than a pattern.

  2. The detector is wrong. Of the six highest scorers, four are real financial
     statements: a statement of stockholders' equity, a cash flow statement, a
     balance sheet. The score conflates "dense in numbers, sparse in sentences"
     with "navigation", and that describes a balance sheet exactly. Every chunk
     immediately below the threshold is a consolidated statement.

Filtering at any threshold that catches the two genuine contents pages also
deletes the statements the corpus exists to answer questions about. The measured
cost of the problem is smaller than the measured cost of the cure.

The module is kept because the measurement is the finding. A decision not to act,
with the number that justifies it, is worth more than an unexamined filter.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("nav")

# Phrases that only appear in navigation furniture.
_NAV_MARKERS = re.compile(
    r"table of contents|^\s*index\b|\bsee page\b|\bpage \d+\s*$", re.I | re.M)

# "Note 4" / "Item 7A" followed closely by a page number is a contents line.
_ENTRY_AND_PAGE = re.compile(r"\b(?:note|item|part)\s+\d{1,2}[A-C]?\b[^.]{0,60}?\b\d{1,3}\b",
                             re.I)

_SENTENCE_END = re.compile(r"[.!?]\s")


def navigation_score(text: str) -> tuple[float, dict]:
    """
    A score in [0,1]. High means the text is a list of pointers, not prose.

    Three independent signals, because any one alone misfires:

      entry density   contents entries per hundred words. Financial tables have
                      numbers but not "Note 4 ... 55" patterns.
      sentence rate   sentences per hundred words. A contents page has almost
                      none; a balance sheet has few; risk factors have many.
      markers         literal "Table of Contents", "INDEX", "see page".

    Sentence rate alone would condemn every financial statement, which is why it
    is never used by itself.
    """
    words = text.split()
    n_words = max(len(words), 1)

    entries = len(_ENTRY_AND_PAGE.findall(text))
    entry_density = min(entries / n_words * 100 / 4.0, 1.0)

    sentences = len(_SENTENCE_END.findall(text))
    sentence_rate = sentences / n_words * 100
    sparse_prose = min(max(1.5 - sentence_rate, 0) / 1.5, 1.0)

    markers = min(len(_NAV_MARKERS.findall(text)) / 2.0, 1.0)

    score = 0.45 * entry_density + 0.25 * sparse_prose + 0.30 * markers
    return score, {"entries": entries, "sentences": sentences,
                   "words": n_words, "markers": len(_NAV_MARKERS.findall(text))}


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure navigation chunks")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--show", type=int, default=6)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("""
        select c.chunk_id, d.ticker, c.item_section, c.token_count, c.content
        from chunks c join documents d using (doc_id)
    """)
    rows = cur.fetchall()

    scored = []
    for chunk_id, ticker, section, tokens, content in rows:
        score, parts = navigation_score(content)
        scored.append((score, chunk_id, ticker, section, tokens, content, parts))
    scored.sort(reverse=True, key=lambda r: r[0])

    print(f"{len(rows):,} chunks scored\n")

    print("proportion of the corpus above each threshold")
    print(f"{'threshold':>10}{'chunks':>10}{'share':>9}")
    print("-" * 29)
    for t in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        n = sum(1 for r in scored if r[0] >= t)
        print(f"{t:>10.1f}{n:>10,}{n / len(rows):>8.1%}")

    print(f"\n{'=' * 78}")
    print(f"HIGHEST SCORING — check these really are navigation")
    print("=" * 78)
    for score, chunk_id, ticker, section, tokens, content, parts in scored[:args.show]:
        print(f"\n  {score:.2f}  chunk {chunk_id}  {ticker} {section}  "
              f"{tokens} tok  ({parts['entries']} entries, "
              f"{parts['sentences']} sentences, {parts['markers']} markers)")
        print(f"    {' '.join(content.split())[:150]}...")

    print(f"\n{'=' * 78}")
    print(f"JUST BELOW THE THRESHOLD OF {args.threshold} — the ones a filter would keep")
    print("=" * 78)
    near = [r for r in scored if r[0] < args.threshold][:args.show]
    for score, chunk_id, ticker, section, tokens, content, parts in near:
        print(f"\n  {score:.2f}  chunk {chunk_id}  {ticker} {section}")
        print(f"    {' '.join(content.split())[:150]}...")

    flagged = [r for r in scored if r[0] >= args.threshold]
    by_section: dict[str, int] = {}
    for r in flagged:
        by_section[r[3] or "-"] = by_section.get(r[3] or "-", 0) + 1

    print(f"\n{'=' * 78}")
    print(f"At {args.threshold}: {len(flagged):,} chunks "
          f"({len(flagged) / len(rows):.1%}) would be filtered")
    for section, n in sorted(by_section.items()):
        cur.execute("select count(*) from chunks where item_section = %s", (section,))
        total = cur.fetchone()[0] or 1
        print(f"    {section:<10} {n:>5} of {total:>5}  ({n / total:>5.1%} of the section)")

    print("\nNothing has been filtered. Whether removing these improves Recall@k")
    print("is a question for src/evaluate_retrieval.py, run before and after.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
