#!/usr/bin/env python3
"""
For every gold label: is the anchor where the label says, elsewhere, or gone?

    python diagnose_labels.py

WHY

`src/verify_labels.py` reports that 23 of 127 labels no longer hold, prints the
first ten and stops. Its message -- "exists as chunk_id N but no longer contains
X" -- says the position resolves and the content does not. It does not say
whether the content is still in the document.

That distinction decides everything:

  moved      the anchor is in another chunk of the same document. The evidence
             exists, the label points at the wrong place, and the fix is
             mechanical. If the offsets share a constant, one cause moved them.

  missing    the anchor is in no chunk of that document. Then the document is
             not the one that was labelled, and the corpus is not the corpus the
             published figures were measured against.

Reads data/chunks.json and eval/questions_vnext.yaml. No database, no network,
and nothing is written: this is a diagnosis, and relabelling before it is done
would destroy the only evidence of what happened.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHUNKS = ROOT / "data" / "chunks.json"
QUESTIONS = ROOT / "eval" / "questions_vnext.yaml"


def flat(text: str) -> str:
    """Whitespace-flattened and lowercased, the way the anchor gate compares."""
    return " ".join(str(text).split()).lower()


def load_chunks() -> dict[str, dict[int, str]]:
    raw = json.loads(CHUNKS.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else (
        raw.get("chunks") or raw.get("records") or [])
    if not rows:
        raise SystemExit(f"{CHUNKS.name}: no chunk list found. "
                         f"Top-level: {sorted(raw) if isinstance(raw, dict) else type(raw)}")
    sample = rows[0]
    for key in ("content", "text", "chunk_text", "body"):
        if key in sample:
            content_key = key
            break
    else:
        raise SystemExit(f"no content field. Keys: {sorted(sample)}")

    by_doc: dict[str, dict[int, str]] = defaultdict(dict)
    for row in rows:
        by_doc[row["doc_id"]][int(row["chunk_index"])] = flat(row[content_key])
    print(f"{len(rows)} chunks in {len(by_doc)} documents "
          f"(content field `{content_key}`)")
    return by_doc


def main() -> int:
    import yaml

    if not CHUNKS.is_file():
        raise SystemExit(f"{CHUNKS} not found. Run src/chunk.py first.")
    by_doc = load_chunks()
    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))

    holds, moved, missing, no_anchor, no_doc = [], [], [], [], []

    for q in questions:
        if not q.get("answerable"):
            continue
        for g in (q.get("gold_chunks") or []):
            qid, doc = q["id"], g["doc_id"]
            idx, anchor = int(g["chunk_index"]), g.get("contains")
            chunks = by_doc.get(doc)
            if chunks is None:
                no_doc.append((qid, doc, idx))
                continue
            if not anchor:
                no_anchor.append((qid, doc, idx))
                continue
            needle = flat(anchor)
            if needle in chunks.get(idx, ""):
                holds.append((qid, doc, idx))
                continue
            where = sorted(i for i, text in chunks.items() if needle in text)
            if where:
                moved.append((qid, doc, idx, where, anchor))
            else:
                missing.append((qid, doc, idx, anchor))

    total = len(holds) + len(moved) + len(missing) + len(no_anchor) + len(no_doc)
    print(f"\n{total} labels\n"
          f"  anchor where the label says      {len(holds)}\n"
          f"  anchor elsewhere in the document {len(moved)}\n"
          f"  anchor in no chunk of it         {len(missing)}\n"
          f"  no anchor to check               {len(no_anchor)}\n"
          f"  document absent from the corpus  {len(no_doc)}")

    if moved:
        print("\n== MOVED: the evidence is there, the label is not ==")
        deltas = Counter()
        for qid, doc, idx, where, anchor in moved:
            nearest = min(where, key=lambda w: abs(w - idx))
            deltas[nearest - idx] += 1
            print(f"  {qid:<7} {doc:<18} says {idx:>4} -> found at "
                  f"{','.join(map(str, where[:4]))}"
                  f"{' ...' if len(where) > 4 else ''}"
                  f"   ({nearest - idx:+d})")
        print("\n  offsets:", ", ".join(f"{d:+d} x{n}"
                                        for d, n in deltas.most_common()))
        if len(deltas) == 1:
            print("  One offset for every label. A single change moved them all,\n"
                  "  and the repair is arithmetic rather than judgement.")
        else:
            print("  The offsets differ, so this is not one shift. Each label\n"
                  "  needs its own look, and a re-chunk is the likely cause.")

    if missing:
        print("\n== MISSING: the anchor is in no chunk of that document ==")
        print("   This is the serious kind. The document is not the one that was")
        print("   labelled, or the anchor text was never in it.")
        for qid, doc, idx, anchor in missing:
            print(f"  {qid:<7} {doc:<18} chunk {idx:<4} '{anchor[:52]}'")

    if no_doc:
        print("\n== DOCUMENT ABSENT ==")
        for qid, doc, idx in no_doc:
            print(f"  {qid:<7} {doc}")

    print("\nNothing was changed. Do not relabel until the counts above are\n"
          "explained: a repair applied now removes the evidence of the cause.")
    return 1 if (moved or missing or no_doc) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
