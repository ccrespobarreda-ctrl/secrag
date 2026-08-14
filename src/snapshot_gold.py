#!/usr/bin/env python3
"""
Photograph the gold chunks before a reparse, and find them again after.

    python src/snapshot_gold.py                 # before: write the snapshot
    python src/snapshot_gold.py --relocate      # after:  find where each went
    python src/snapshot_gold.py --relocate --write   # ... and fix questions.yaml

WHY THIS EXISTS

gold_chunks pins a label to (doc_id, chunk_index) and checks it with `contains`.
That works, and it is why 57 of the 88 labels can announce their own breakage.

The other 31 have no `contains` -- the answer is a prose paraphrase, or the only
anchors available were the company name and a bare year, which verify nothing.
Those 31 resolve to whatever now sits at that index and say nothing about it.

The reparse in tanda 2 trims the tail of every section. Chunk boundaries inside
a section do not move, because chunk_section accumulates paragraphs from the
start -- but chunk_index runs across the whole document, so one lost chunk in
Item 1 shifts every index after it, and most gold labels live in Item 8, the
last section indexed.

So the text is photographed while the database still holds it. Afterwards each
label is found again by matching that text, not by trusting the number.

HOW THE MATCHING WORKS

Probes: distinctive lines taken from the stored content, spread across it rather
than all from the opening, because the opening is what a trimmed tail leaves
untouched and a shifted label would match on it by accident.

A candidate scores the fraction of probes it contains. Only chunks of the same
doc_id are considered -- a label never migrates between filings, and letting it
would turn a shift into a wrong answer with a confident score.

Nothing is rewritten unless --write is passed, and then only labels that matched
confidently. Everything else is printed for reading, which is the honest outcome:
this reduces the relabeling to the cases that genuinely need a person.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import labels as L  # noqa: E402

log = logging.getLogger("snapshot")

DEFAULT_SNAPSHOT = "eval/gold_snapshot.json"

# A probe shorter than this matches too much: "Total net revenues" appears in
# every filing in the corpus.
PROBE_MIN_CHARS = 45
PROBE_COUNT = 8

# Fraction of probes a candidate must contain to be accepted without a person
# reading it. Below this the label is reported, not rewritten.
CONFIDENT = 0.60

# A candidate this close to the best one means the chunk was split or duplicated
# and the choice is not mechanical.
AMBIGUOUS_MARGIN = 0.15


def probes(content: str) -> list[str]:
    """
    Distinctive fragments of a chunk, spread across its whole length.

    Sentence-ish pieces rather than fixed windows, so a probe survives the
    whitespace differences a reparse introduces. Normalised the same way
    labels.normalise does, because that is what the comparison will use.
    """
    pieces = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", content)]
    pieces = [L.normalise(p) for p in pieces if len(p.strip()) >= PROBE_MIN_CHARS]

    if not pieces:
        # A chunk with no sentence structure -- a financial table flattened into
        # one line. Cut fixed windows instead.
        body = L.normalise(content)
        pieces = [body[i:i + 120] for i in range(0, len(body), 200)]
        pieces = [p for p in pieces if len(p) >= PROBE_MIN_CHARS]

    if len(pieces) <= PROBE_COUNT:
        return pieces

    # Evenly spaced, not the first N: the head of a section is the part a
    # tail-trimming reparse leaves alone, so head-only probes cannot tell a
    # surviving chunk from its neighbour.
    step = len(pieces) / PROBE_COUNT
    return [pieces[int(i * step)] for i in range(PROBE_COUNT)]


def gold_entries(questions: list[dict]) -> list[dict]:
    """Every (question, doc_id, chunk_index) label in the file."""
    out = []
    for q in questions:
        for entry in q.get("gold_chunks") or []:
            out.append({
                "id": q["id"],
                "doc_id": entry.get("doc_id"),
                "chunk_index": entry.get("chunk_index"),
                "contains": entry.get("contains"),
            })
    return out


def dump(cur, questions: list[dict], out_path: Path) -> int:
    entries = gold_entries(questions)
    if not entries:
        log.error("No gold_chunks in %s. Run src/migrate_labels.py first.",
                  C.EVAL_QUESTIONS)
        return 1

    records, missing = [], []
    for e in entries:
        cur.execute("""
            select chunk_id, content, token_count, item_section
            from chunks where doc_id = %s and chunk_index = %s
        """, (e["doc_id"], e["chunk_index"]))
        row = cur.fetchone()

        if row is None:
            missing.append(e)
            continue

        chunk_id, content, token_count, section = row
        records.append({
            **e,
            "chunk_id": chunk_id,
            "item_section": section,
            "token_count": token_count,
            "n_chars": len(content),
            "probes": probes(content),
            "content": content,
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "note": ("Text of every gold chunk as it stood before the reparse. "
                 "Used by --relocate to find each label again by content."),
        "n_labels": len(records),
        "records": records,
    }, indent=1), encoding="utf-8")

    unanchored = sum(1 for r in records if not r["contains"])
    print(f"{len(records)} gold chunks photographed -> {out_path}")
    print(f"  {len(records) - unanchored} carry a `contains` anchor and can "
          f"report their own breakage")
    print(f"  {unanchored} have none, and are the reason this file exists")

    if missing:
        print(f"\n{len(missing)} label(s) do not resolve against the current "
              f"corpus, and were not photographed:")
        for e in missing:
            print(f"  {e['id']:<7} {e['doc_id']} chunk {e['chunk_index']}")
        return 1
    return 0


def relocate(cur, snapshot: dict, questions: list[dict], write: bool,
             questions_path: Path) -> int:
    records = snapshot["records"]

    # One query per filing rather than per label: 88 labels concentrate into
    # about a dozen documents.
    by_doc: dict[str, list[tuple[int, str]]] = {}
    for doc_id in sorted({r["doc_id"] for r in records}):
        cur.execute("""
            select chunk_index, content from chunks
            where doc_id = %s order by chunk_index
        """, (doc_id,))
        by_doc[doc_id] = [(i, L.normalise(c)) for i, c in cur.fetchall()]

    same = moved = ambiguous = lost = 0
    fixes: dict[tuple[str, int], int] = {}
    report: list[str] = []

    for r in records:
        candidates = by_doc.get(r["doc_id"], [])
        if not candidates:
            lost += 1
            report.append(f"  {r['id']:<7} {r['doc_id']} is not in the corpus "
                          f"at all")
            continue

        if not r["probes"]:
            lost += 1
            report.append(f"  {r['id']:<7} {r['doc_id']} chunk "
                          f"{r['chunk_index']}: too short to probe, read it")
            continue

        scored = []
        for index, body in candidates:
            hits = sum(1 for p in r["probes"] if p in body)
            scored.append((hits / len(r["probes"]), index))
        scored.sort(reverse=True)

        best_score, best_index = scored[0]
        runner = scored[1][0] if len(scored) > 1 else 0.0

        if best_score < CONFIDENT:
            lost += 1
            report.append(
                f"  {r['id']:<7} {r['doc_id']} chunk {r['chunk_index']}: best "
                f"match scores {best_score:.2f} at index {best_index} — below "
                f"the threshold, read it")
            continue

        if best_score - runner < AMBIGUOUS_MARGIN:
            ambiguous += 1
            report.append(
                f"  {r['id']:<7} {r['doc_id']} chunk {r['chunk_index']}: "
                f"{best_index} ({best_score:.2f}) and {scored[1][1]} "
                f"({runner:.2f}) match almost equally — the chunk was split")
            continue

        if best_index == r["chunk_index"]:
            same += 1
        else:
            moved += 1
            fixes[(r["doc_id"], r["chunk_index"])] = best_index
            report.append(
                f"  {r['id']:<7} {r['doc_id']} chunk {r['chunk_index']} "
                f"-> {best_index}  (score {best_score:.2f})"
                + ("" if r["contains"] else "   <-- had no anchor; this shift "
                                            "would have been silent"))

    total = len(records)
    print(f"\n{total} labels relocated by content\n")
    print(f"{'still at the same index':<34}{same:>5}")
    print(f"{'moved, matched confidently':<34}{moved:>5}")
    print(f"{'ambiguous, chunk was split':<34}{ambiguous:>5}")
    print(f"{'not found, needs reading':<34}{lost:>5}")

    if report:
        print("\nWorth reading:")
        for line in report:
            print(line)

    if not write:
        print("\nNothing written. Pass --write to apply the confident moves.")
        return 0 if not lost and not ambiguous else 1

    if not fixes:
        print("\nNo confident moves to apply.")
        return 0

    applied = 0
    for q in questions:
        for entry in q.get("gold_chunks") or []:
            key = (entry.get("doc_id"), entry.get("chunk_index"))
            if key in fixes:
                entry["chunk_index"] = fixes[key]
                applied += 1

    import yaml
    backup = Path(str(questions_path) + ".pre-relocate")
    backup.write_bytes(questions_path.read_bytes())
    questions_path.write_text(
        yaml.safe_dump(questions, sort_keys=False, allow_unicode=True,
                       width=100, default_flow_style=False),
        encoding="utf-8")

    print(f"\n{applied} chunk_index values updated in {questions_path}")
    print(f"Original copied to {backup}")
    print("\nRun src/verify_labels.py now: the labels that carry an anchor will "
          "confirm\nthemselves, and the ones that do not are listed above.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Photograph gold chunks, and find them again after a reparse")
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT, type=Path)
    ap.add_argument("--relocate", action="store_true",
                    help="find the photographed chunks in the current corpus")
    ap.add_argument("--write", action="store_true",
                    help="with --relocate, apply the confident moves")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    questions = L.load(args.questions)

    if not args.relocate:
        if args.snapshot.exists():
            log.error("%s already exists. Photographing again would overwrite "
                      "the pre-reparse text with the post-reparse text, which "
                      "is the one thing this file must never contain. Delete it "
                      "by hand if that is really what you want.", args.snapshot)
            conn.close()
            return 2
        code = dump(cur, questions, args.snapshot)
    else:
        if not args.snapshot.exists():
            log.error("%s not found. It has to be written BEFORE the reparse.",
                      args.snapshot)
            conn.close()
            return 2
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        code = relocate(cur, snapshot, questions, args.write, args.questions)

    conn.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
