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

WHAT AN ANCHOR HAS TO DO, AND HOW THAT IS TESTED

An anchor exists so a label can fail. If the corpus is re-chunked and the label
drifts, the anchor should stop matching; if it goes on matching, the label is
unfalsifiable and every figure measured against it rests on a check that cannot
fail.

The only property that tests this is how many chunks of the document the anchor
matches. One is ideal. A handful is normal — a revenue total legitimately
appears in the income statement, the segment note and the MD&A of one filing,
and the 60-token overlap duplicates text across boundaries. A hundred means the
anchor is decoration.

An intermediate version of this check tried to excuse an anchor that carried a
word of the labelled answer, on the grounds that "6,165,376" cannot be unique
and is obviously good. That was wrong, and the data says why: "Wayfair" also
appears in the labelled answer to a question about Wayfair, and it matches 108
chunks. Content does not separate the two. The match count does — five against
a hundred and eight — and it is the only signal that does.

So the gate counts matches and nothing else. The count carrying the answer is
still reported, because it says what an anchor would catch if the chunk lost the
figure, but it does not excuse anything.

The format and the resolution both live in src/labels.py; this is the report.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import labels as L  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("verify_labels")

_STOP = {"the", "a", "an", "of", "and", "or", "in", "to", "for", "our", "we",
         "is", "are", "was", "were", "as", "at", "on", "by", "with", "that",
         "this", "its", "it", "from", "which", "their", "has", "have"}


def _norm(word: str) -> str:
    """A labelled answer writes "$6,165,376"; the filing writes "6,165,376"."""
    return word.strip("$\u20ac\u00a3.,;:()[]\"'").lower()


def _answer_words(gold_answer: str | None) -> set[str]:
    """Content words of the answer. Figures are kept whatever their length."""
    if not gold_answer:
        return set()
    out = set()
    for raw in re.findall(r"[\w,\.%$\u20ac\u00a3]+", gold_answer):
        w = _norm(raw)
        if not w or w in _STOP:
            continue
        if any(c.isdigit() for c in w) or len(w) > 2:
            out.add(w)
    return out


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
    ap.add_argument("--max-anchor-matches", type=int, default=0,
                    help="fail if an anchor matches more chunks than this "
                         "(0 reports without failing)")
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

    # How many chunks of the same document each anchor matches. An anchor that
    # matches many is not evidence about a position, and every figure measured
    # against that label rests on a check that cannot fail.
    anchor_counts = []
    for q in labeled:
        answer = _answer_words(q.get("gold_answer"))
        for g in (q.get("gold_chunks") or []):
            anchor = g.get("contains")
            if not anchor:
                continue
            cur.execute("""select count(*) from chunks
                           where doc_id = %s and content ilike %s""",
                        (g["doc_id"], f"%{anchor}%"))
            n = cur.fetchone()[0]
            carried = len({_norm(w) for w in anchor.split()} & answer)
            anchor_counts.append((q["id"], g["doc_id"], anchor, n, carried))
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

    if anchor_counts:
        uniq = sum(1 for r in anchor_counts if r[3] <= 1)
        few = sum(1 for r in anchor_counts if 2 <= r[3] <= 8)
        many = [r for r in anchor_counts if r[3] > 8]
        carrying = sum(1 for r in anchor_counts if r[4])
        print(f"\n{'anchors matching one chunk':<40}{uniq:>5}")
        print(f"{'  two to eight':<40}{few:>5}   "
              f"(overlap, and figures that repeat)")
        print(f"{'  more than eight':<40}{len(many):>5}   "
              f"(cannot say which chunk)")
        print(f"{'anchors carrying the labelled answer':<40}{carrying:>5}   "
              f"(would catch a lost figure)")
        if many:
            print("\nThese match too many chunks to identify one, so they stay "
                  "satisfied\nwherever the label points:")
            for qid, doc_id, anchor, n, _ in sorted(
                    many, key=lambda r: -r[3])[:args.show]:
                print(f"  {qid:<7} {doc_id:<18} {anchor[:34]!r} in {n} chunks")
            if len(many) > args.show:
                print(f"  ... {len(many) - args.show} more")

    over = [r for r in anchor_counts
            if args.max_anchor_matches and r[3] > args.max_anchor_matches]

    if not problems and not over:
        severe_n = sum(1 for r in anchor_counts if r[3] > 8)
        print("\nEvery label resolves and every anchor is still in its chunk.")
        if args.max_anchor_matches:
            print(f"No anchor matches more than {args.max_anchor_matches} "
                  f"chunks of its document.")
        elif severe_n:
            # Saying only the first sentence would be true and misleading at
            # once: the anchors above resolve, and cannot fail. Reporting a
            # clean result beside a list of unverifiable labels is the kind of
            # half-statement this harness exists to prevent.
            print(f"That is a weaker statement than it reads: {severe_n} "
                  f"anchors match more than\neight chunks, so they would "
                  f"resolve wherever their label pointed. Run with\n"
                  f"--max-anchor-matches 8 to treat that as a failure.")
        return 0

    if over and not problems:
        print(f"\n{len(over)} anchor(s) match more than "
              f"{args.max_anchor_matches} chunks of their document.\nEvery "
              f"label resolves, but these cannot say which chunk they mean. "
              f"Fix them\nby hand, or with src/fix_anchors.py.")
        for qid, doc_id, anchor, n, _ in over:
            print(f"  {qid:<7} {doc_id:<18} {anchor[:40]!r} in {n} chunks")
        return 1

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
