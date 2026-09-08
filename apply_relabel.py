#!/usr/bin/env python3
"""
Move each broken gold label to the chunk holding the identical text.

    python apply_relabel.py --dry-run     # say what would change
    python apply_relabel.py --apply       # change it, and write the log

THE RULE, WRITTEN BEFORE IT WAS RUN

A label moves if and only if:

  1. its anchor is not inside the chunk the label names, in data/chunks.json;
  2. tests/fixture_corpus.json holds the text that position had when the
     figures were published;
  3. exactly one chunk of the same document in data/chunks.json has content
     identical to it once whitespace is flattened.

Anything else is left alone and printed. Zero identical candidates means the
text changed and a person has to read the filing. Two or more means identity
does not discriminate and neither does this rule.

WHY IDENTITY AND NOT PROXIMITY

Nearest-index would be wrong. Q029's release chunk is identical to chunk 80 and
the nearest candidate is 79, which the 60-token overlap makes nearly the same
text and not the same chunk. Q001's anchor appears in five chunks of Urban
Outfitters' filing -- the income statement, the segment table, the category
table -- and the notes in the question file record that the segment table was
rejected by hand in August, "3517 descartado: tiene la cifra desglosada por
categoria, sin la linea de total". A rule that chased the anchor or the nearest
index could land there and quietly undo a decision someone made by reading.

Identity discriminates where proximity does not, and it is checkable: across
the 295 fixture chunks, 294 have exactly one identical counterpart in the
corpus and none has two, so the mapping is injective.

WHY THIS IS NOT THE AUTOMATION check_neighbours.py REFUSED

That script would not accept a neighbouring chunk as evidence, because deciding
that a different chunk carries the same evidence is a judgement, and a rule that
made it silently would inflate every figure in the project. This does not judge
evidence. It asserts that two byte-identical texts are the same passage, and it
declines every case where that is not exactly true.

WHAT IT DOES NOT DO

It does not re-measure anything, rebuild the fixture, or touch the derived split
files. Those are separate steps, and the published 0.735 was measured against
the labels as they were: whatever comes out afterwards is a new figure and is
published as one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "tests" / "fixture_corpus.json"
CORPUS = ROOT / "data" / "chunks.json"
QUESTIONS = ROOT / "eval" / "questions_vnext.yaml"
LOG = ROOT / "docs" / "relabel-log.md"

ID_LINE = re.compile(r"^-\s+id:\s*(\S+)\s*$")
DOC_LINE = re.compile(r"^(\s*)-?\s*doc_id:\s*(\S+)\s*$")
IDX_LINE = re.compile(r"^(\s*)chunk_index:\s*(\d+)\s*$")


def flat(text: str) -> str:
    return " ".join(str(text).split())


def rows_of(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else (
        raw.get("chunks") or raw.get("records") or [])


def content_index(rows: list[dict]) -> dict[tuple[str, int], str]:
    out = {}
    for row in rows:
        for key in ("content", "text", "chunk_text", "body"):
            if key in row:
                out[(row["doc_id"], int(row["chunk_index"]))] = flat(row[key])
                break
    return out


def main() -> int:
    import yaml

    ap = argparse.ArgumentParser(description="Relabel by identical content")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    for path in (FIXTURE, CORPUS, QUESTIONS):
        if not path.is_file():
            raise SystemExit(f"{path} not found")

    fixture = content_index(rows_of(FIXTURE))
    corpus = content_index(rows_of(CORPUS))

    # content -> the positions holding it, per document
    where: dict[tuple[str, str], list[int]] = {}
    for (doc, idx), text in corpus.items():
        where.setdefault((doc, text), []).append(idx)

    orphan = [key for key, text in fixture.items()
              if not where.get((key[0], text))]

    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    moves: dict[tuple[str, str, int], int] = {}
    skipped: list[tuple[str, str, int, str]] = []

    for q in questions:
        if not q.get("answerable"):
            continue
        for g in (q.get("gold_chunks") or []):
            anchor, doc = g.get("contains"), g["doc_id"]
            idx = int(g["chunk_index"])
            if not anchor:
                continue
            if flat(anchor).lower() in corpus.get((doc, idx), "").lower():
                continue                          # the label still holds

            release = fixture.get((doc, idx))
            if release is None:
                skipped.append((q["id"], doc, idx,
                                "the fixture has no text for this position"))
                continue
            found = sorted(where.get((doc, release), []))
            if len(found) == 1:
                if found[0] != idx:
                    moves[(q["id"], doc, idx)] = found[0]
            elif not found:
                skipped.append((q["id"], doc, idx,
                                "no chunk has identical content: the text "
                                "changed, read the filing"))
            else:
                skipped.append((q["id"], doc, idx,
                                f"identical content in {len(found)} chunks "
                                f"{found}: identity does not decide"))

    print(f"{len(moves)} label(s) move, {len(skipped)} left for a person")
    for (qid, doc, idx), new in sorted(moves.items()):
        print(f"  {qid:<7} {doc:<18} {idx:>4} -> {new:<4} ({new - idx:+d})")
    for qid, doc, idx, why in skipped:
        print(f"  SKIP  {qid:<7} {doc:<18} {idx:>4}  {why}")
    if orphan:
        print(f"\n{len(orphan)} fixture chunk(s) have no identical counterpart "
              f"in the corpus:")
        for doc, idx in orphan:
            print(f"  {doc:<18} chunk {idx}   (a neighbour unless it appears above)")
        print("  Their text changed. None of the moves above depends on them.")

    if args.dry_run:
        print("\nDry run. Nothing was written.")
        return 0
    if not moves:
        print("\nNothing to apply.")
        return 0

    # Line-surgical edit: only the digits of chunk_index change, so the notes,
    # the key order and the anchors stay byte-identical. Rewriting the file
    # through yaml.dump would reformat every entry and lose the comments.
    # open() rather than Path.read_text(newline=...), which is 3.13+. The file
    # is CRLF and every byte outside the digits being changed must survive.
    with open(QUESTIONS, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    before = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    lines = raw.splitlines(keepends=True)
    qid = doc = None
    applied = []

    for i, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        m = ID_LINE.match(stripped)
        if m:
            qid, doc = m.group(1), None
            continue
        m = DOC_LINE.match(stripped)
        if m:
            doc = m.group(2)
            continue
        m = IDX_LINE.match(stripped)
        if m and qid and doc:
            idx = int(m.group(2))
            new = moves.get((qid, doc, idx))
            if new is not None:
                ending = line[len(stripped):]
                lines[i] = f"{m.group(1)}chunk_index: {new}{ending}"
                applied.append((qid, doc, idx, new))

    if len(applied) != len(moves):
        print(f"\nRefusing to write: {len(moves)} moves planned, "
              f"{len(applied)} lines matched. The file's shape is not what this "
              f"edit assumes.")
        return 1

    with open(QUESTIONS, "w", encoding="utf-8", newline="") as fh:
        fh.write("".join(lines))
    with open(QUESTIONS, encoding="utf-8", newline="") as fh:
        after = hashlib.sha256(fh.read().encode("utf-8")).hexdigest()

    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = [
        "# Relabelling log",
        "",
        f"Applied {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by "
        f"`apply_relabel.py --apply`.",
        "",
        "## The rule",
        "",
        "A label moved if and only if its anchor was no longer inside the chunk",
        "it named, `tests/fixture_corpus.json` held the text that position had",
        "when the figures were published, and exactly one chunk of the same",
        "document in `data/chunks.json` had identical content once whitespace was",
        "flattened. Every other case was left alone and is listed below.",
        "",
        "Not proximity: Q029's release text is identical to chunk 80 while the",
        "nearest candidate is 79, and Q001's anchor appears in five chunks of the",
        "same filing, one of which was rejected by hand in August.",
        "",
        "## What changed",
        "",
        f"`{QUESTIONS.relative_to(ROOT).as_posix()}`",
        "",
        f"- before: `{before}`",
        f"- after:  `{after}`",
        "",
        "| Question | Document | Was | Now | Offset |",
        "|---|---|---:|---:|---:|",
    ]
    log += [f"| {qid} | `{doc}` | {idx} | {new} | {new - idx:+d} |"
            for qid, doc, idx, new in applied]
    if skipped:
        log += ["", "## Left for a person", "",
                "| Question | Document | Chunk | Why |", "|---|---|---:|---|"]
        log += [f"| {qid} | `{doc}` | {idx} | {why} |"
                for qid, doc, idx, why in skipped]
    if orphan:
        log += ["", "## Fixture chunks with no identical counterpart", "",
                "Their text changed between the release corpus and the corpus on",
                "disk. No move above depends on them.", ""]
        log += [f"- `{doc}` chunk {idx}" for doc, idx in orphan]
    log += [
        "", "## What has not been done yet", "",
        "1. `python src/verify_labels.py --questions eval/questions_vnext.yaml"
        " --max-anchor-matches 8 --max-exceptions 4`",
        "2. Delete and regenerate the derived split files: they carry copies of",
        "   these indices. Then `python src/derive_split.py --verify`.",
        "3. `python tests/fixture.py --build`, so the fixture stops being the",
        "   only record of the old corpus and starts describing this one.",
        "4. Re-measure retrieval. **The published 0.735 was measured against the",
        "   labels as they were, over a corpus of 4,169 chunks that this pipeline",
        "   no longer produces.** Whatever comes out is a new figure and is",
        "   published as a new figure, with this log as the reason.",
        "",
    ]
    LOG.write_text("\n".join(log), encoding="utf-8")
    print(f"\napplied {len(applied)} moves")
    print(f"wrote {LOG.relative_to(ROOT).as_posix()}")
    print("\nNo figure has been re-measured. Step 1 of the log is next.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
