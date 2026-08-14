#!/usr/bin/env python3
"""
Search the corpus, and compare the three retrieval paths side by side.

    python src/search.py "supplier concentration risk"
    python src/search.py "total revenue fiscal 2025" --section "Item 8"
    python src/search.py "does the company rely on one manufacturer" --compare

--compare runs semantic, keyword and hybrid over the same question and prints
what each one found.

WHAT HYBRID ACTUALLY BUYS

An earlier version of this tool counted results found by only one path, on the
assumption that those were hybrid's contribution. Measured on real questions the
count was zero, every time, and the reason is that RRF is built to reward
consensus:

    a chunk at semantic #2 and keyword #39   ->  1/62 + 1/99 = 0.0263
    a chunk at semantic #1 and nowhere else  ->  1/61        = 0.0164

Agreement between two independent rankings beats a strong showing in one. So
hybrid does not surface documents neither path found; it reorders by how much
the two paths agree. The comparison below measures that instead: how far
hybrid's ordering departs from each path taken alone.

THE QUERY PREFIX

bge models are trained asymmetrically. Passages are embedded raw; queries are
prefixed with an instruction:

    "Represent this sentence for searching relevant passages: {query}"

Omitting it on the query side, or applying it on the passage side, puts the two
in different spaces and degrades recall with no error to point at. src/embed.py
deliberately does not use it; this module deliberately does.
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

log = logging.getLogger("search")

_model = None


def embed_query(text: str) -> list[float]:
    """Embed a question the way the encoder expects to receive one."""
    global _model
    if _model is None:
        for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(C.EMBEDDING_MODEL, device="cpu")

    vector = _model.encode(
        C.QUERY_PREFIX + text,          # prefix on the query side only
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vector.tolist()


def show(title: str, hits: list[R.Hit], width: int = 96) -> None:
    print(f"\n{title}")
    print("-" * width)
    if not hits:
        print("  nothing found")
        return
    for i, h in enumerate(hits, 1):
        ranks = []
        if h.semantic_rank:
            ranks.append(f"sem #{h.semantic_rank}")
        if h.keyword_rank:
            ranks.append(f"kw #{h.keyword_rank}")
        rank_note = f"  [{', '.join(ranks)}]" if ranks else ""
        print(f"  {i}. {h.ticker} FY{h.fiscal_year} {h.item_section or '':<8} "
              f"score {h.score:.5f}{rank_note}")
        body = " ".join(h.content.split())
        print(f"     {body[:width - 5]}...")


def main() -> int:
    ap = argparse.ArgumentParser(description="Search the SEC corpus")
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=C.RETRIEVAL_TOP_K)
    ap.add_argument("--section", action="append",
                    help="restrict to an Item, repeatable")
    ap.add_argument("--compare", action="store_true",
                    help="run all three paths, not just hybrid")
    ap.add_argument("--rrf", type=int, default=C.RRF_K,
                    help="fusion constant; lower favours top ranks over consensus")
    ap.add_argument("--sweep", action="store_true",
                    help="show the hybrid top-3 across several fusion constants")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select count(*) from chunks where embedding is not null")
    n = cur.fetchone()[0]
    if not n:
        log.error("No embedded chunks in the warehouse — run src/load.py first")
        return 2

    print(f"query    {args.query!r}")
    print(f"corpus   {n:,} chunks", end="")
    if args.section:
        print(f"  ·  restricted to {', '.join(args.section)}", end="")
    print()

    qv = embed_query(args.query)

    if args.compare:
        expr = R._keyword_expression(cur, args.query, args.section)
        mode = "AND" if expr is R._AND_TSQUERY else "OR (AND was too thin)"
        show("SEMANTIC ONLY — cosine distance over the vectors",
             R.search_semantic(cur, qv, top_k=args.k, sections=args.section))
        show(f"KEYWORD ONLY — Postgres full-text search, {mode}",
             R.search_keyword(cur, args.query, top_k=args.k,
                              sections=args.section, expression=expr))

    hits = R.search_hybrid(cur, args.query, qv, top_k=args.k,
                           rrf_k=args.rrf, sections=args.section)
    show(f"HYBRID — reciprocal rank fusion, k={args.rrf}", hits)

    if args.sweep:
        # k controls how much appearing in both lists is worth against ranking
        # highly in one. The published value of 60 comes from TREC experiments,
        # not from this corpus, and on factual questions it lets a chunk that is
        # mediocre in both paths outrank one that is first in a single path.
        print("\n  hybrid top-3 across fusion constants")
        print("  " + "-" * 92)
        for k in (5, 10, 20, 40, 60):
            top = R.search_hybrid(cur, args.query, qv, top_k=3,
                                  rrf_k=k, sections=args.section)
            line = "  |  ".join(
                f"{h.ticker} {h.item_section} (s{h.semantic_rank or '-'}/"
                f"k{h.keyword_rank or '-'})" for h in top)
            print(f"    k={k:<3} {line}")
        print("\n  Which constant is right is a question for the harness.")

    if args.compare and hits:
        sem_top = {h.chunk_id for h in
                   R.search_semantic(cur, qv, top_k=args.k, sections=args.section)}
        kw_top = {h.chunk_id for h in
                  R.search_keyword(cur, args.query, top_k=args.k, sections=args.section)}
        hy_top = {h.chunk_id for h in hits}

        print(f"\n  top-{args.k} overlap")
        print(f"    semantic and keyword agree on   {len(sem_top & kw_top)}/{args.k}")
        print(f"    hybrid keeps from semantic      {len(hy_top & sem_top)}/{args.k}")
        print(f"    hybrid keeps from keyword       {len(hy_top & kw_top)}/{args.k}")
        print(f"    hybrid promoted from deeper     "
              f"{len(hy_top - sem_top - kw_top)}/{args.k}")

        deeper = [h for h in hits if h.chunk_id not in sem_top | kw_top]
        if deeper:
            print("    promoted purely by agreement, outside either top-k:")
            for h in deeper:
                print(f"      {h.ticker} {h.item_section:<8} "
                      f"sem #{h.semantic_rank}, kw #{h.keyword_rank}")

        print("\n  Whether that reordering helps is a question for the evaluation")
        print("  harness, not for three hand-picked queries.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
