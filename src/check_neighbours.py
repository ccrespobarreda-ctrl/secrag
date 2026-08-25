#!/usr/bin/env python3
"""
When a gold chunk is missed, look at what arrived in its place.

    python src/check_neighbours.py --id Q034
    python src/check_neighbours.py --type comparative --window 2

A missed label is not the same event as a missed answer. Section-aware chunking
with a 60-token overlap can put a risk-factor heading in one chunk and its whole
development in the next, and the labeller, reading to find where the answer
begins, marks the heading. The retriever then does what it should -- it finds the
chunk dense in the words the question uses, which is the one that follows -- and
Recall@k records a failure that did not happen.

So for every missed gold, this reports whether an adjacent chunk from the same
document arrived instead, and prints enough of it to judge whether it answers the
question. That judgement stays with a person: an automatic rule that quietly
accepted neighbours would inflate every figure in the project, which is the exact
failure mode documented in docs/measurement-honesty.md.

It also counts, over the whole corpus, how often a chunk ends on what looks like
the start of a new topic -- the structural defect this exists to detect.
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
import retrieve as R  # noqa: E402

log = logging.getLogger("neighbours")

# A 10-K risk factor opens with a full sentence in the imperative or conditional
# — "Changes in tariff policy ... could adversely affect our business." A chunk
# whose last sentences look like that, with nothing after them, is a chunk that
# ends on a heading.
_HEADING_TAIL = re.compile(
    r"(?:could|may|might|would)\s+(?:continue to\s+)?"
    r"(?:adversely\s+)?(?:affect|harm|impact|disrupt|result in)\b[^.]*\.\s*$",
    re.IGNORECASE)


def preview(text: str, width: int = 320, needle: str | None = None) -> str:
    body = " ".join(text.split())
    start = 0
    if needle:
        pos = body.lower().find(needle.lower())
        if pos > width // 2:
            start = pos - width // 3
    return ("..." if start else "") + body[start:start + width] + "..."


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Inspect what arrived instead of a missed gold chunk")
    ap.add_argument("--questions", type=Path,
                    default=Path("eval/questions_vnext_regression.yaml"))
    ap.add_argument("--id", action="append", help="restrict to question ids")
    ap.add_argument("--type", help="restrict to a question type")
    ap.add_argument("-k", type=int, default=C.RETRIEVAL_TOP_K)
    ap.add_argument("--window", type=int, default=1,
                    help="how many chunks either side count as adjacent")
    ap.add_argument("--scan", action="store_true",
                    help="also count chunks corpus-wide that end on a heading")
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
            if q.get("answerable") and q.get("gold_chunk_ids")]
    if args.id:
        wanted = {i.upper() for i in args.id}
        rows = [q for q in rows if q["id"].upper() in wanted]
    if args.type:
        rows = [q for q in rows if q["type"] == args.type]
    if not rows:
        print("No questions matched.")
        return 1

    n_missed = n_neighbour = 0

    for q in rows:
        gold = set(q["gold_chunk_ids"])
        hits = R.search(cur, q["question"], embed_query(q["question"]),
                        top_k=args.k)
        got = {h.chunk_id for h in hits}
        missed = gold - got
        if not missed:
            continue

        print(f"\n{'=' * 74}\n{q['id']}  {q['question']}")
        for cid in sorted(missed):
            n_missed += 1
            cur.execute("""select doc_id, chunk_index from chunks
                           where chunk_id = %s""", (cid,))
            row = cur.fetchone()
            if not row:
                continue
            doc_id, idx = row

            cur.execute("""select chunk_id, chunk_index, item_section,
                                  token_count, content
                           from chunks
                           where doc_id = %s and chunk_index between %s and %s
                           order by chunk_index""",
                        (doc_id, idx - args.window, idx + args.window))
            family = cur.fetchall()

            print(f"\n  gold {cid} — {doc_id} chunk_index {idx}, MISSED")
            found_neighbour = False
            for ncid, nidx, section, tokens, content in family:
                if ncid == cid:
                    tag = "the label"
                elif ncid in got:
                    tag = "RETRIEVED INSTEAD"
                    found_neighbour = True
                else:
                    tag = "not retrieved"
                print(f"\n    chunk {ncid:<6} index {nidx:<4} {section or '-':<9}"
                      f"{tokens:>4}t   {tag}")
                print(f"      {preview(content)}")
            if found_neighbour:
                n_neighbour += 1
                print("\n    -> an adjacent chunk from the same document "
                      "arrived. Read both\n       above and decide whether the "
                      "question is answered. If it is, the\n       label is on "
                      "the wrong side of a chunk boundary.")

    print(f"\n{'=' * 74}")
    print(f"{n_missed} missed gold chunks, {n_neighbour} with an adjacent "
          f"chunk retrieved instead")
    if n_missed:
        print(f"  {n_neighbour / n_missed:.0%} of misses may be boundary "
              f"artifacts rather than retrieval failures.\n  Whether they are "
              f"is a judgement to make by reading, not a rule to apply.")

    if args.scan:
        cur.execute("select chunk_id, doc_id, item_section, content from chunks")
        rows_all = cur.fetchall()
        ends_on_heading = [r for r in rows_all if _HEADING_TAIL.search(r[3])]
        print(f"\nCorpus scan: {len(ends_on_heading)} of {len(rows_all)} chunks "
              f"({len(ends_on_heading) / len(rows_all):.1%}) end on what reads\n"
              f"  like the opening sentence of a new risk factor, with none of "
              f"its body.")
        by_section = {}
        for _, _, section, _ in ends_on_heading:
            by_section[section or "-"] = by_section.get(section or "-", 0) + 1
        for s, n in sorted(by_section.items(), key=lambda x: -x[1])[:6]:
            print(f"    {s:<12}{n:>5}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
