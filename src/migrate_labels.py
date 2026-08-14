#!/usr/bin/env python3
"""
Rewrite eval/questions.yaml from serial chunk_ids to durable labels. Run once.

    python src/migrate_labels.py --dry-run     # see what it would write
    python src/migrate_labels.py

RUN THIS BEFORE RELOADING, NOT AFTER

The translation is mechanical only while the database still holds the chunks the
labels were written against:

    select doc_id, chunk_index from chunks where chunk_id = 3518

Once the corpus is reloaded from a different chunking, 3518 resolves to different
text or to nothing, and the same translation has to be done by reading filings
with src/find_gold.py -- which is the two afternoons the labels cost in the first
place.

So the order matters, and it is the opposite of the intuitive one:

    1. python src/migrate_labels.py      against the corpus as it stands now
    2. apply the parser changes
    3. make chunk && make embed && make load
    4. make verify-labels                which now resolves the new format

WHAT IT WRITES

    gold_chunk_ids: [3236, 3294]

becomes

    gold_chunks:
      - {doc_id: UAA-10-K-2026, chunk_index: 212, contains: "4,966,370"}
      - {doc_id: UAA-10-K-2026, chunk_index: 231, contains: "Total net revenues"}

The `contains` string is derived from gold_answer and then CHECKED against the
chunk before being written. An anchor that does not appear is not written, and
the label is reported instead: writing an anchor that was never verified would
build the guarantee out of an assumption.

Nothing is destroyed. The original file is copied to questions.yaml.bak, and
gold_chunk_ids is kept alongside gold_chunks as a record of what the labels were
before, so the migration can be read and argued with rather than trusted.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import labels as L  # noqa: E402

log = logging.getLogger("migrate_labels")


def pick_anchor(cur, chunk_id: int, gold_answer: str, content: str
                ) -> tuple[str | None, str]:
    """
    The strongest anchor from the answer that actually appears in the chunk.

    Returns (anchor, note). A None anchor is not a failure of the migration --
    the doc_id and chunk_index still migrate, and the label is simply one that
    cannot be checked automatically afterwards.
    """
    body = L.normalise(content)

    for candidate in L.anchors(gold_answer):
        if L.normalise(candidate) in body:
            return candidate, "strong"

    for candidate in L.weak_anchors(gold_answer):
        if L.normalise(candidate) in body:
            return candidate, "weak"

    if L.anchors(gold_answer) or L.weak_anchors(gold_answer):
        return None, "no anchor from the answer appears in the chunk"
    return None, "the answer yields no anchor (prose paraphrase)"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Migrate gold labels to doc_id + chunk_index + contains")
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("--out", type=Path, help="default: rewrite in place")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    import yaml

    questions = L.load(args.questions)
    already = [q["id"] for q in questions if q.get("gold_chunks")]
    if already and len(already) == len([q for q in questions if q.get("answerable")]):
        print("Every answerable question already uses gold_chunks. Nothing to do.")
        return 0

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select count(*) from chunks")
    n_chunks = cur.fetchone()[0]
    print(f"Translating against the corpus as it stands: {n_chunks:,} chunks\n")

    migrated = unresolved = weak = unanchored = 0
    notes: list[str] = []

    for q in questions:
        ids = q.get("gold_chunk_ids") or []
        if not q.get("answerable") or not ids or q.get("gold_chunks"):
            continue

        spec = []
        for chunk_id in ids:
            cur.execute("""
                select c.doc_id, c.chunk_index, c.content
                from chunks c where c.chunk_id = %s
            """, (chunk_id,))
            row = cur.fetchone()

            if row is None:
                unresolved += 1
                notes.append(
                    f"  {q['id']:<7} chunk_id {chunk_id} is not in the corpus. "
                    f"The database was reloaded after labeling; this one has to "
                    f"be relabeled by reading.")
                continue

            doc_id, index, content = row
            anchor, note = pick_anchor(cur, chunk_id, q.get("gold_answer") or "",
                                       content)

            entry = {"doc_id": doc_id, "chunk_index": index}
            if anchor:
                entry["contains"] = anchor
                if note == "weak":
                    weak += 1
                    notes.append(f"  {q['id']:<7} {doc_id} chunk {index}: only a "
                                 f"short figure to anchor on ({anchor!r})")
            else:
                unanchored += 1
                notes.append(f"  {q['id']:<7} {doc_id} chunk {index}: {note}")

            spec.append(entry)
            migrated += 1

        if spec:
            q["gold_chunks"] = spec

    conn.close()

    print(f"{'labels translated':<28}{migrated:>5}")
    print(f"{'  with a strong anchor':<28}{migrated - weak - unanchored:>5}")
    print(f"{'  with a weak anchor':<28}{weak:>5}")
    print(f"{'  with no anchor':<28}{unanchored:>5}")
    print(f"{'labels that did not resolve':<28}{unresolved:>5}")

    if notes:
        print("\nWorth reading before this is committed:")
        for line in notes:
            print(line)

    if unresolved:
        print("\nA label that does not resolve cannot be migrated mechanically. "
              "Those\nare the ones that cost an afternoon, and there is no way "
              "around it:\n\n    python src/find_gold.py \"the question\" "
              "--expect \"the answer\"")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    out = args.out or args.questions
    if out == args.questions:
        backup = Path(str(args.questions) + ".bak")
        shutil.copy2(args.questions, backup)
        print(f"\nOriginal copied to {backup}")

    # sort_keys=False so the reading order written by hand survives, and
    # allow_unicode so the Spanish notes are not escaped into \\uXXXX.
    Path(out).write_text(
        yaml.safe_dump(questions, sort_keys=False, allow_unicode=True,
                       width=100, default_flow_style=False),
        encoding="utf-8")
    print(f"Written to {out}")
    print("\ngold_chunk_ids is kept alongside gold_chunks, as a record of what "
          "the\nlabels were. src/labels.py ignores it once gold_chunks exists.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
