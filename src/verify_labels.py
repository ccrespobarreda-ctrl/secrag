#!/usr/bin/env python3
"""
Confirm every gold label still points at the text it was written for.

    python src/verify_labels.py
    python src/verify_labels.py --show 12

Run it after every load, before trusting any retrieval number.

WHAT IT CATCHES

A label is a claim about the corpus: "the answer to Q002 is in UAA-10-K-2026,
chunk 212, and that chunk contains 4,966,370". Reloading, re-chunking or
re-parsing can each falsify that claim, and none of them raises anything.
Retrieval still returns chunks, the harness still prints a Recall@k, and the
number is measured against labels pointing somewhere else.

Three ways a claim fails, and they need different responses:

    missing   the filing was re-chunked into fewer pieces, so that index is gone
    moved     the chunk exists and no longer contains the answer
    legacy    the label is still a bare chunk_id, which guarantees none of this

The format and the resolution both live in src/labels.py; this is the report.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import labels as L  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("verify_labels")


def company_mismatches(cur, questions: list[dict]) -> list[dict]:
    """
    The company named in the question against the ticker the chunks belong to.

    Independent of the anchors, and cheap. When labels shift, the ticker usually
    shifts with them, which catches the ones whose anchors are too generic to
    test -- or absent, as they are for a prose paraphrase.
    """
    out = []
    for q in questions:
        expected = set(R.detect_companies(q.get("question", "")))
        ids = q.get("gold_chunk_ids") or []
        if not expected or not ids:
            continue

        cur.execute("""
            select distinct d.ticker from chunks c
            join documents d using (doc_id) where c.chunk_id = any(%s)
        """, (ids,))
        actual = {r[0] for r in cur.fetchall()}

        if actual and not (expected & actual):
            out.append({
                "id": q["id"], "kind": "wrong company",
                "detail": (f"question names {sorted(expected)}, labeled chunks "
                           f"belong to {sorted(actual)}"),
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Confirm gold labels still hold their answers")
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2

    questions = L.load(args.questions)
    labeled = [q for q in questions if q.get("answerable")]
    if not labeled:
        print("No answerable questions to check.")
        return 2

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select count(*) from chunks")
    n_chunks = cur.fetchone()[0]

    problems = L.resolve(cur, questions)
    problems += company_mismatches(cur, labeled)
    conn.close()

    expected_labels = sum(len(q.get("gold_chunks") or q.get("gold_chunk_ids") or [])
                          for q in labeled)
    resolved = sum(len(q.get("gold_chunk_ids") or []) for q in labeled)
    unanchored = [q["id"] for q in labeled
                  for e in (q.get("gold_chunks") or []) if not e.get("contains")]

    print(f"{expected_labels} gold labels across {len(labeled)} questions, "
          f"against {n_chunks:,} chunks\n")
    print(f"{'resolved':<28}{resolved:>5}")
    print(f"{'  without an anchor':<28}{len(unanchored):>5}   "
          f"(position checked, content not)")
    print(f"{'failed':<28}{expected_labels - resolved:>5}")

    if unanchored:
        print("\nThese resolve by position but carry no `contains`, so a chunk "
              "whose\ntext changed underneath them would pass. Read them:")
        for qid in sorted(set(unanchored)):
            print(f"  {qid}")

    if not problems:
        print("\nEvery label resolves and every anchor is still in its chunk.")
        return 0

    by_kind = defaultdict(list)
    for p in problems:
        by_kind[p["kind"]].append(p)

    print(f"\n{'=' * 70}")
    print("LABELS THAT NO LONGER HOLD")
    print("=" * 70)
    print("Every retrieval metric measured against these is meaningless.\n")

    for kind in sorted(by_kind):
        rows = by_kind[kind]
        print(f"{kind}  ({len(rows)})")
        for p in rows[:args.show]:
            print(f"  {p['id']:<7} {p['detail']}")
        if len(rows) > args.show:
            print(f"  ... {len(rows) - args.show} more")
        print()

    if "legacy" in by_kind:
        print("Migrate the bare ids while the corpus they were written against "
              "is still\nloaded — after a reload the translation has to be done "
              "by reading:\n\n    python src/migrate_labels.py\n")

    print("Otherwise relabel:  python src/find_gold.py \"the question\" "
          "--expect \"the answer\"")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
