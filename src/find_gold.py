#!/usr/bin/env python3
"""
Find candidate gold chunks while labeling questions.

    python src/find_gold.py "What were Under Armour's net revenues in fiscal 2026?"
    python src/find_gold.py "..." --expect "4,966,370"
    python src/find_gold.py "..." --ticker UAA --section "Item 8"

Prints candidates with their chunk ids and enough text to judge them, so a label
can be assigned by reading rather than by guessing at SQL.

A WARNING ABOUT WHAT THIS TOOL CANNOT DO

It uses the same retriever the evaluation is meant to test. Taking its first
result as the gold label measures the retriever against itself and guarantees a
perfect score.

--expect exists to break that circularity: give the answer string you already
know, and the tool searches the whole corpus for it directly, independently of
retrieval ranking. Any chunk containing it is a candidate regardless of where
the retriever placed it — including chunks the retriever missed entirely, which
are exactly the labels that make Recall@k mean something.

Use --expect wherever the answer is a figure or a distinctive phrase. Read the
candidates either way.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("find_gold")


# 400 rather than 150. Measured over the first six questions labeled, every
# single one required a follow-up --chunk call because the answer fell past the
# preview: a figure sitting after its column headers, an auditor's signature at
# the end of a report, a fiscal year end buried in a paragraph of definitions.
# Doubling the preview removes most of that round trip.
def print_chunk(chunk_id, ticker, year, section, content, note="", width=400,
                highlight=None):
    """
    Show the part of the chunk that matters.

    When a search string is known, the window is centred on it rather than on
    the start of the chunk. A figure two thousand characters in is invisible in a
    preview that always begins at character zero, and that is precisely where
    financial tables put their numbers.
    """
    print(f"\n  chunk_id {chunk_id}   {ticker} FY{year}  {section or '-'}   {note}")
    body = " ".join(content.split())

    start = 0
    if highlight:
        pos = body.lower().find(highlight.lower())
        if pos > width // 2:
            start = pos - width // 3

    excerpt = body[start:start + width]
    prefix = "..." if start else ""
    suffix = "..." if start + width < len(body) else ""
    print(f"    {prefix}{excerpt}{suffix}")


def literal_search(cur, needle: str, ticker: str | None, limit: int):
    """
    Find the answer string anywhere in the corpus, ignoring the retriever.

    This is the label source that keeps the evaluation honest: it can surface a
    chunk the retriever ranks 400th, and that chunk is still the correct answer.
    """
    clauses = ["c.content ilike %(needle)s"]
    params = {"needle": f"%{needle}%", "limit": limit}
    if ticker:
        clauses.append("d.ticker = %(ticker)s")
        params["ticker"] = ticker.upper()

    cur.execute(f"""
        select c.chunk_id, d.ticker, d.fiscal_year, c.item_section, c.content
        from chunks c join documents d using (doc_id)
        where {' and '.join(clauses)}
        order by c.chunk_id
        limit %(limit)s
    """, params)
    return cur.fetchall()


def rank_of(cur, chunk_id: int, query: str, qv, sections) -> str:
    """Where the retriever placed a chunk, for the labeling notes."""
    hits = R.search_hybrid(cur, query, qv, top_k=100, pool=200, sections=sections)
    for i, h in enumerate(hits, 1):
        if h.chunk_id == chunk_id:
            return f"hybrid rank {i}"
    return "not in the top 100"


def main() -> int:
    ap = argparse.ArgumentParser(description="Locate gold chunks for a question")
    ap.add_argument("question")
    ap.add_argument("--expect", help="a string the answer must contain")
    ap.add_argument("--ticker", help="restrict to one company")
    ap.add_argument("--section", action="append", help="restrict to an Item")
    ap.add_argument("-k", type=int, default=6)
    ap.add_argument("--chunk", type=int,
                    help="print one chunk in full, to read it before labeling")
    ap.add_argument("--preview", type=int, default=400,
                    help="characters of each candidate to show")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    # Reading a candidate in full is what separates a label from a guess. The
    # 150-character previews below are for scanning, not for deciding.
    if args.chunk:
        cur.execute("""
            select c.chunk_id, d.ticker, d.company, d.fiscal_year,
                   c.item_section, c.token_count, c.content
            from chunks c join documents d using (doc_id)
            where c.chunk_id = %s
        """, (args.chunk,))
        row = cur.fetchone()
        if not row:
            print(f"chunk {args.chunk} does not exist")
            conn.close()
            return 1
        cid, ticker, company, year, section, tokens, content = row
        print(f"chunk {cid}   {company} ({ticker}) FY{year}   {section}   "
              f"{tokens} tokens\n")
        print(content)
        conn.close()
        return 0

    print(f"question  {args.question!r}")

    literal_ids = []
    if args.expect:
        rows = literal_search(cur, args.expect, args.ticker, args.k * 3)
        print(f"\n{'=' * 76}")
        print(f"LITERAL MATCHES for {args.expect!r} — independent of the retriever")
        print("=" * 76)
        if not rows:
            print("\n  none. Either the phrasing differs from the filing, or the "
                  "answer\n  is genuinely not in the corpus — which makes this an "
                  "unanswerable question.")
        for chunk_id, ticker, year, section, content in rows:
            literal_ids.append(chunk_id)
            print_chunk(chunk_id, ticker, year, section, content,
                        width=args.preview, highlight=args.expect)

    # The retriever's own view, shown second and labeled as such so it is not
    # mistaken for evidence.
    from search import embed_query
    qv = embed_query(args.question)
    hits = R.search_hybrid(cur, args.question, qv, top_k=args.k,
                           sections=args.section)

    print(f"\n{'=' * 76}")
    print("WHAT THE RETRIEVER RETURNS — for reference, not for labeling")
    print("=" * 76)
    for i, h in enumerate(hits, 1):
        mark = "  <-- also a literal match" if h.chunk_id in literal_ids else ""
        print_chunk(h.chunk_id, h.ticker, h.fiscal_year, h.item_section,
                    h.content, note=f"rank {i}{mark}", width=args.preview)

    if literal_ids:
        print(f"\n{'=' * 76}")
        print("WHERE THE RETRIEVER PLACED EACH LITERAL MATCH")
        print("=" * 76)
        for chunk_id in literal_ids[:6]:
            where = rank_of(cur, chunk_id, args.question, qv, args.section)
            flag = "" if "rank" in where and "not" not in where else "   <-- a miss"
            print(f"  chunk_id {chunk_id:<8} {where}{flag}")
        print("\n  A literal match the retriever misses is the most valuable label")
        print("  in the set: it is exactly what Recall@k is supposed to catch.")

    print(f"\n{'=' * 76}")
    print("Read the candidates, then put the id of the chunk that genuinely")
    print("contains the answer into gold_chunk_ids in eval/questions.yaml.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
