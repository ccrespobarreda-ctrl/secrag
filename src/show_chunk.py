#!/usr/bin/env python3
"""
Print a chunk, addressed the way a label addresses it.

    python src/show_chunk.py URBN-10-K-2026 121
    python src/show_chunk.py ANF-10-K-2026 53 --neighbours
    python src/show_chunk.py --id 3903

src/find_gold.py takes a chunk_id, which is a serial number assigned at load
time. A gold label points at a document and an index inside it, because that
pair survives a reload and the serial does not. Writing an anchor by hand means
reading the chunk the label names, so this takes the same address the label
uses.

--neighbours prints the chunk either side as well, which is what you want when
the question is whether a label sits on the wrong side of a chunk boundary.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

log = logging.getLogger("show_chunk")


_DOC_CACHE: dict[str, list[str]] = {}


def _flat(text: str) -> str:
    """Collapse every run of whitespace, the way a reader sees the text."""
    return " ".join(text.split())


def document_chunks(cur, doc_id: str) -> list[str]:
    """
    Every chunk of a document, whitespace-flattened, loaded once.

    Two reasons, and the first is correctness. The raw text carries the line
    breaks of a filing's tables: "Old Navy Global 3 %" is stored with newlines
    between the cells. Anything read off a printed chunk has single spaces, so
    comparing it against the raw column finds nothing, and reports an anchor
    that is plainly there as matching zero chunks. Both sides are flattened
    before comparing.

    The second is speed. Growing an anchor word by word asked the database once
    per step; a document is four hundred kilobytes and fits in memory, so the
    whole search now runs without a round trip.
    """
    if doc_id not in _DOC_CACHE:
        cur.execute("select content from chunks where doc_id = %s "
                    "order by chunk_index", (doc_id,))
        _DOC_CACHE[doc_id] = [_flat(r[0]) for r in cur.fetchall()]
    return _DOC_CACHE[doc_id]


def count_matches(cur, doc_id: str, needle: str) -> int:
    """How many chunks contain this text, comparing flattened to flattened."""
    n = _flat(needle).lower()
    if not n:
        return 0
    return sum(1 for c in document_chunks(cur, doc_id) if n in c.lower())


def show(row, width: int, highlight: str | None) -> None:
    chunk_id, doc_id, idx, section, tokens, content = row
    print(f"\n{'=' * 78}")
    print(f"{doc_id}  index {idx}   chunk_id {chunk_id}   "
          f"{section or '-'}   {tokens} tokens")
    print("=" * 78)
    body = " ".join(content.split())
    if highlight and highlight.lower() in body.lower():
        i = body.lower().index(highlight.lower())
        print(f"  [anchor at character {i} of {len(body)}]")
    print(body[:width] + ("..." if len(body) > width else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="Print a chunk by document and index")
    ap.add_argument("doc_id", nargs="?")
    ap.add_argument("chunk_index", nargs="?", type=int)
    ap.add_argument("--id", type=int, help="address by chunk_id instead")
    ap.add_argument("--neighbours", action="store_true",
                    help="also print the chunk either side")
    ap.add_argument("--width", type=int, default=2200)
    ap.add_argument("--find", help="report where this string sits in the chunk")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2
    if args.id is None and (not args.doc_id or args.chunk_index is None):
        ap.error("give a doc_id and chunk_index, or --id")

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cols = "chunk_id, doc_id, chunk_index, item_section, token_count, content"
    if args.id is not None:
        cur.execute(f"select {cols} from chunks where chunk_id = %s", (args.id,))
    else:
        cur.execute(f"select {cols} from chunks where doc_id = %s "
                    f"and chunk_index = %s", (args.doc_id, args.chunk_index))
    row = cur.fetchone()
    if not row:
        print("No such chunk.")
        conn.close()
        return 1

    doc_id, idx = row[1], row[2]
    lo = idx - 1 if args.neighbours else idx
    hi = idx + 1 if args.neighbours else idx
    cur.execute(f"select {cols} from chunks where doc_id = %s "
                f"and chunk_index between %s and %s order by chunk_index",
                (doc_id, lo, hi))
    for r in cur.fetchall():
        show(r, args.width, args.find)

    if args.find:
        n = count_matches(cur, doc_id, args.find)
        if n == 0:
            verdict = ("  — MATCHES NOTHING. The text is not in this document "
                       "as written;\n    check spacing and punctuation before "
                       "using it")
        elif n <= 8:
            verdict = "  — good anchor"
        else:
            verdict = "  — too many to identify one chunk"
        print(f"\n  {args.find!r} matches {n} chunk(s) of {doc_id}{verdict}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
