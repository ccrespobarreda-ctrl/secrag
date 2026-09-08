#!/usr/bin/env python3
"""
Why is continuous integration green while verify_labels fails locally?

    python check_fixture_vs_corpus.py

THE CONTRADICTION

tests/fixture.py --check asserts that every gold anchor sits inside the chunk
its label names. .github/workflows/ci.yml runs it on every push and it passes.
Run the same assertion against data/chunks.json and 23 of 127 labels fail.

Both cannot be true of the same text, so the two are not looking at the same
text. tests/fixture_corpus.json is committed: it was built by
`fixture.py --build` from whatever corpus was in the warehouse that day, and it
has not been rebuilt since. data/chunks.json on this machine is dated 14 August
and holds 4,124 chunks; FINAL_RELEASE_MANIFEST.md says the release had 4,169.

This compares them chunk by chunk, for the labelled positions only, and says
which of the two the labels agree with. It reads two files and writes nothing.

WHAT THE ANSWER DECIDES

  the fixture holds the labelled text, the corpus on disk does not
      The committed fixture is the release corpus. The gate passes because it
      is checking the corpus the labels were written for, and it can never
      notice that the pipeline now produces a different one. That is the gate
      being immune to the failure it exists to catch, and it is the same shape
      as finding 7.

  both hold it, or neither does
      Then the fixture is not the explanation and the green build has another
      cause, which has to be found before anything is repaired.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "tests" / "fixture_corpus.json"
CORPUS = ROOT / "data" / "chunks.json"
QUESTIONS = ROOT / "eval" / "questions_vnext.yaml"


def flat(text: str) -> str:
    return " ".join(str(text).split()).lower()


def index(rows: list[dict]) -> dict[tuple[str, int], str]:
    out = {}
    for row in rows:
        for key in ("content", "text", "chunk_text", "body"):
            if key in row:
                out[(row["doc_id"], int(row["chunk_index"]))] = flat(row[key])
                break
    return out


def rows_of(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else (
        raw.get("chunks") or raw.get("records") or [])


def main() -> int:
    import yaml

    for path in (FIXTURE, CORPUS, QUESTIONS):
        if not path.is_file():
            raise SystemExit(f"{path} not found")

    fixture_rows, corpus_rows = rows_of(FIXTURE), rows_of(CORPUS)
    fixture, corpus = index(fixture_rows), index(corpus_rows)
    print(f"fixture  {len(fixture_rows):>6} chunks   ({FIXTURE.relative_to(ROOT).as_posix()})")
    print(f"corpus   {len(corpus_rows):>6} chunks   ({CORPUS.relative_to(ROOT).as_posix()})")

    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    labels = [(q["id"], g) for q in questions if q.get("answerable")
              for g in (q.get("gold_chunks") or []) if g.get("contains")]

    both, only_fixture, only_corpus, neither, absent = [], [], [], [], []
    differing_text = 0

    for qid, g in labels:
        key = (g["doc_id"], int(g["chunk_index"]))
        needle = flat(g["contains"])
        in_fix = key in fixture and needle in fixture[key]
        in_cor = key in corpus and needle in corpus[key]
        if key not in fixture:
            absent.append((qid, key))
        elif key in corpus and fixture[key] != corpus[key]:
            differing_text += 1

        if in_fix and in_cor:
            both.append(qid)
        elif in_fix:
            only_fixture.append((qid, key))
        elif in_cor:
            only_corpus.append((qid, key))
        else:
            neither.append((qid, key))

    print(f"\n{len(labels)} labels with an anchor")
    print(f"  anchor holds in both                 {len(both)}")
    print(f"  holds in the fixture only            {len(only_fixture)}")
    print(f"  holds in the corpus on disk only     {len(only_corpus)}")
    print(f"  holds in neither                     {len(neither)}")
    print(f"  labelled chunk absent from fixture   {len(absent)}")
    print(f"\n  labelled chunks whose text differs between the two: "
          f"{differing_text}")

    if only_fixture:
        print("\n== These pass in CI and fail on disk ==")
        for qid, (doc, idx) in only_fixture:
            print(f"  {qid:<7} {doc:<18} chunk {idx}")
        print(
            "\nThe committed fixture holds the text these labels were written\n"
            "against; the pipeline no longer produces it. The gate cannot fail,\n"
            "because fixture.py --build extracted the chunks the labels name and\n"
            "nothing rebuilds it when the corpus changes. A green build does not\n"
            "mean the measurements can be trusted, which is what ci.yml says it\n"
            "means."
        )
    elif neither:
        print("\n== These fail in both ==")
        for qid, (doc, idx) in neither:
            print(f"  {qid:<7} {doc:<18} chunk {idx}")
        print("\nThe fixture is not the explanation for the green build.")
    else:
        print("\nEvery anchor holds in both. The fixture and the corpus agree,\n"
              "and the green build has some other cause.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
