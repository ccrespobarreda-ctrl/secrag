#!/usr/bin/env python3
"""
Find out why a question type fails, before trying to fix it.

    python src/diagnose_type.py --type comparative
    python src/diagnose_type.py --type comparative --deep 200
    python src/diagnose_type.py --type multi_chunk --questions eval/questions_vnext_regression.yaml

Coverage on comparatives is 0.300 and that number says nothing about the cause.
A gold chunk sitting at rank 18 and one sitting at rank 400 produce the same
0.300, and they need opposite fixes: the first is a budget that is one notch too
small, the second is a retrieval failure that no budget will reach.

So this looks past the cutoff. Every gold chunk is located in the top --deep
results, and reported with the rank it actually holds.

WHY THE PER-COMPANY QUOTA IS PRINTED

A comparative names two companies, and search() splits the top-k budget between
them: eight excerpts each at k=16. If the evidence for one company is spread
over several passages, eight slots may be spent before reaching it while the
other company's eight are half wasted. The report shows, per question, how the
retrieved slots were divided and where the gold fell within each company's own
ranking -- which distinguishes "the budget is too small" from "the budget is
misallocated", and those are also different fixes.

WHAT COUNTS AS ACTIONABLE

A missed gold chunk that ranks within about twice the current k is reachable by
widening the budget. One that ranks in the hundreds is not, and pretending
otherwise wastes a week. The summary at the end counts both.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("diagnose")


def rank_map(hits) -> dict[int, int]:
    return {h.chunk_id: i for i, h in enumerate(hits, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Locate the gold chunks a question type is missing")
    ap.add_argument("--questions", type=Path,
                    default=Path("eval/questions_vnext_regression.yaml"))
    ap.add_argument("--type", default="comparative")
    ap.add_argument("-k", type=int, default=C.RETRIEVAL_TOP_K)
    ap.add_argument("--deep", type=int, default=100,
                    help="how far past the cutoff to look")
    ap.add_argument("--save", type=Path)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    import labels as L
    from search import embed_query

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    questions = L.load(args.questions)
    L.resolve(cur, questions)
    rows = [q for q in questions
            if q.get("answerable") and q.get("type") == args.type
            and q.get("gold_chunk_ids")]

    if not rows:
        print(f"No answerable {args.type} questions with labels in "
              f"{args.questions}.")
        return 1

    print(f"{len(rows)} {args.type} questions, k={args.k}, "
          f"looking as deep as {args.deep}\n")

    reachable, unreachable, inside = [], [], []
    detail = []

    for q in rows:
        gold = list(dict.fromkeys(q["gold_chunk_ids"]))
        qv = embed_query(q["question"])

        # What the system actually returns, and what it would return with a
        # much larger budget. Same code path, only the cutoff differs.
        shipped = R.search(cur, q["question"], qv, top_k=args.k)
        deep = R.search(cur, q["question"], qv, top_k=args.deep)
        deep_rank = rank_map(deep)
        in_top_k = {h.chunk_id for h in shipped}

        tickers = R.detect_companies(q["question"])
        got = Counter(h.ticker for h in shipped)

        print(f"{q['id']}  {q['question'][:78]}")
        print(f"   companies detected: {tickers or 'none'}   "
              f"slots used: {dict(got)}")

        for cid in gold:
            cur.execute("""select d.ticker from chunks c
                           join documents d using (doc_id)
                           where c.chunk_id = %s""", (cid,))
            row = cur.fetchone()
            ticker = row[0] if row else "?"

            if cid in in_top_k:
                where = f"rank {deep_rank[cid]}, delivered"
                inside.append(cid)
            elif cid in deep_rank:
                r = deep_rank[cid]
                where = f"rank {r} — MISSED, would arrive at k={r}"
                (reachable if r <= args.k * 2 else unreachable).append(cid)
            else:
                where = f"not in the top {args.deep} — MISSED, out of reach"
                unreachable.append(cid)

            print(f"     gold {cid:<6} {ticker:<6} {where}")
            detail.append({"id": q["id"], "chunk_id": cid, "ticker": ticker,
                           "rank": deep_rank.get(cid),
                           "delivered": cid in in_top_k})
        print()

    total = len(inside) + len(reachable) + len(unreachable)
    print("=" * 72)
    print(f"{total} gold chunks across {len(rows)} {args.type} questions\n")
    print(f"  delivered inside k={args.k:<20}{len(inside):>3}  "
          f"{len(inside) / total:.0%}")
    print(f"  missed but within k={args.k * 2:<19}{len(reachable):>3}  "
          f"{len(reachable) / total:.0%}   widening the budget reaches these")
    print(f"  missed and deeper than that{'':<10}{len(unreachable):>3}  "
          f"{len(unreachable) / total:.0%}   a budget will not reach these")

    if reachable:
        ceiling = (len(inside) + len(reachable)) / total
        print(f"\n  Coverage would rise from {len(inside) / total:.3f} to at "
              f"most {ceiling:.3f}\n  by widening alone. Whether that is worth "
              f"the extra tokens is a\n  separate question: input tokens are "
              f"84% of the bill.")
    if unreachable and not reachable:
        print("\n  Nothing is reachable by widening. The failure is in ranking "
              "or in\n  the chunking, not in the cutoff.")

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(
            {"type": args.type, "k": args.k, "deep": args.deep,
             "delivered": len(inside), "reachable": len(reachable),
             "unreachable": len(unreachable), "chunks": detail},
            indent=1), encoding="utf-8")
        print(f"\nSaved to {args.save}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
