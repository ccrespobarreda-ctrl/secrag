#!/usr/bin/env python3
"""
Check that every gold anchor identifies its chunk, and propose better ones.

    python src/audit_anchors.py
    python src/audit_anchors.py --questions eval/questions_vnext.yaml --propose
    python src/audit_anchors.py --strict          # exit 1 if any anchor is weak

WHAT verify_labels CANNOT SEE

A label says: the answer to Q014 is in URBN-10-K-2026, chunk 119, and that chunk
contains "Deloitte". verify_labels confirms the anchor is still inside the chunk
after a reload, and reports every label as holding.

It cannot confirm the anchor identifies that chunk rather than a dozen others.
"Deloitte" appears wherever the auditor is named. "Connected" appears throughout
a Peloton filing. "Wayfair" appears in almost every chunk Wayfair wrote. An
anchor like that survives any re-chunking no matter where the label ends up
pointing, which is precisely the drift the check exists to catch.

So this counts, for every anchor, how many chunks of the same document contain
it. One is what a label should mean. Twenty means the anchor is decoration.

THE PROPOSED REPLACEMENT

--propose searches the labeled chunk for the longest span that appears in it and
nowhere else in the document, preferring spans that contain a digit, because a
figure is both distinctive and the thing most questions are actually about.

Proposals are printed, never written. An anchor rewritten automatically is an
anchor nobody read, and the labels are the one part of this benchmark that has
to be human.
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

log = logging.getLogger("anchors")


def count_in_document(cur, doc_id: str, needle: str) -> int:
    cur.execute("""select count(*) from chunks
                   where doc_id = %s and content ilike %s""",
                (doc_id, f"%{needle}%"))
    return cur.fetchone()[0]


_STOP = {"the", "a", "an", "of", "and", "or", "in", "to", "for", "our", "we",
         "is", "are", "was", "were", "as", "at", "on", "by", "with", "that",
         "this", "its", "it", "from", "which", "their", "has", "have"}


def answer_words(gold_answer: str | None) -> set[str]:
    if not gold_answer:
        return set()
    return {w for w in re.findall(r"[\w,\.%$]+", gold_answer.lower())
            if w not in _STOP and len(w) > 2}


def candidate_spans(text: str, answer: set[str], min_words: int = 4,
                    max_words: int = 12):
    """
    Word spans from the chunk, ranked by how well they anchor the answer.

    An anchor has two jobs and the first version only did one of them. It must
    identify this chunk rather than a dozen others -- and it must also confirm
    the chunk still contains the answer. A span can be perfectly unique and
    useless: proposing "We have served as the Company's auditor since 2005" as
    the anchor for a question about gross profit would leave verify_labels
    reporting a healthy label for a chunk that had lost the figure.

    So the ranking is: how many words of the labelled answer the span carries,
    then whether it carries a figure, then length. Uniqueness is tested after,
    against the document.
    """
    words = " ".join(text.split()).split(" ")
    spans = []
    for size in range(max_words, min_words - 1, -1):
        for i in range(0, len(words) - size + 1):
            span = " ".join(words[i:i + size])
            if len(span) < 12 or span.strip() == "%":
                continue
            low = set(w.lower() for w in span.split())
            spans.append((len(low & answer), bool(re.search(r"\d", span)),
                          len(span), span))
    spans.sort(reverse=True)
    return [s[3] for s in spans]


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit gold anchor uniqueness")
    ap.add_argument("--questions", type=Path, default=C.EVAL_QUESTIONS)
    ap.add_argument("--propose", action="store_true",
                    help="suggest a unique replacement for every weak anchor")
    ap.add_argument("--limit-scan", type=int, default=1500,
                    help="candidate spans tried per weak anchor")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any anchor matches more than one chunk")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    import labels as L

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    questions = L.load(args.questions)
    L.resolve(cur, questions)

    total = unique = weak = missing = 0
    rows = []

    for q in questions:
        if not q.get("answerable"):
            continue
        for g in (q.get("gold_chunks") or []):
            total += 1
            anchor, doc_id = g.get("contains"), g["doc_id"]
            if not anchor:
                missing += 1
                rows.append((q["id"], doc_id, g["chunk_index"], None, None,
                             q.get("gold_answer")))
                continue
            n = count_in_document(cur, doc_id, anchor)
            if n <= 1:
                unique += 1
            else:
                weak += 1
                rows.append((q["id"], doc_id, g["chunk_index"], anchor, n,
                             q.get("gold_answer")))

    print(f"{total} anchors across the answerable questions\n")
    overlap = sum(1 for r in rows if r[4] and r[4] <= 3)
    severe = sum(1 for r in rows if r[4] and r[4] >= 5)
    mid = weak - overlap - severe

    print(f"  {'unique in their document':<36}{unique:>4}  {unique / total:>5.0%}")
    print(f"  {'in 2-3 chunks (the 60-token overlap)':<36}{overlap:>4}  "
          f"{overlap / total:>5.0%}")
    print(f"  {'in 4 chunks':<36}{mid:>4}  {mid / total:>5.0%}")
    print(f"  {'in 5 or more — cannot verify anything':<36}{severe:>4}  "
          f"{severe / total:>5.0%}")
    print(f"  {'no anchor at all':<36}{missing:>4}  {missing / total:>5.0%}")
    print("\n  The three bands are different problems. Two or three matches is "
          "usually\n  the chunk overlap duplicating text across a boundary, and "
          "the label still\n  points where it should. Five or more means the "
          "anchor would stay satisfied\n  wherever the label drifted to, which "
          "is the failure verify_labels exists\n  to catch and cannot.")

    if not rows:
        conn.close()
        return 0

    print(f"\n{'=' * 74}\nANCHORS THAT DO NOT IDENTIFY THEIR CHUNK\n{'=' * 74}")
    rows.sort(key=lambda r: -(r[4] or 0))
    for qid, doc_id, idx, anchor, n, gold in rows:
        if anchor is None:
            print(f"\n  {qid}  {doc_id} idx {idx}   no anchor — position only")
            continue
        print(f"\n  {qid}  {doc_id} idx {idx}   {anchor!r} matches {n} chunks")

        if not args.propose:
            continue
        cur.execute("""select content from chunks
                       where doc_id = %s and chunk_index = %s""", (doc_id, idx))
        row = cur.fetchone()
        if not row:
            print("      chunk not found")
            continue
        answer = answer_words(gold)
        spans = candidate_spans(row[0], answer)
        tried = 0
        for span in spans[:args.limit_scan]:
            tried += 1
            if count_in_document(cur, doc_id, span) == 1:
                carries = len(set(w.lower() for w in span.split()) & answer)
                note = (f"carries {carries} word(s) of the labelled answer"
                        if carries else
                        "carries none of the answer — positional only, read it "
                        "before using")
                print(f"      suggested: {span!r}\n        {note}")
                break
        else:
            print(f"      no unique span in the first {tried} candidates of "
                  f"{len(spans)}.\n        Raise --limit-scan before concluding "
                  f"anything about this one.")

    conn.close()
    if args.strict and (weak or missing):
        print(f"\n{weak + missing} anchors do not identify a single chunk.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
