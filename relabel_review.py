#!/usr/bin/env python3
"""
Put the release text beside the current corpus, for every label that broke.

    python relabel_review.py

WHY A REVIEW AND NOT A REPAIR

23 of 127 labels no longer hold. diagnose_labels.py found the anchor elsewhere
in the same document for all 23 and in no case missing, so the evidence exists
and only the index is wrong. It would be a short script to move each label to
the nearest match and declare the benchmark fixed.

That is exactly what this project refuses to do. src/check_neighbours.py already
declined to accept a neighbour automatically, with the reason written in it: an
automatic rule that accepted neighbours quietly would inflate every figure in
the project, which is the failure mode measurement-honesty.md documents. The
same argument applies here with more force, because these are the gold labels
themselves.

So this writes a file to read. For each broken label it shows the text the label
was written against -- recovered from tests/fixture_corpus.json, which holds the
release corpus at exactly the labelled positions -- and every candidate in the
corpus on disk, with a blank decision line under each. A person decides. Then
apply_relabel.py acts only on decisions that were written down.

WHERE THE RELEASE TEXT COMES FROM

tests/fixture_corpus.json was built by `fixture.py --build` on 17 August from
the warehouse of the day, and committed. It holds every chunk a gold label
points at plus its neighbours: 295 chunks of the 4,169-chunk corpus the
published figures were measured against. Nothing else in the repository
preserves that text. It is a backup nobody meant to make.

EXACT MATCH IS THE STRONG CASE

When a chunk in the current corpus is byte-identical to the release chunk after
whitespace flattening, the content did not change and only the index did. That
is marked CERTAIN, and it is still shown rather than applied.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "tests" / "fixture_corpus.json"
CORPUS = ROOT / "data" / "chunks.json"
QUESTIONS = ROOT / "eval" / "questions_vnext.yaml"
OUT = ROOT / "docs" / "relabel-review.md"
WINDOW = 320


def flat(text: str) -> str:
    return " ".join(str(text).split())


def rows_of(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else (
        raw.get("chunks") or raw.get("records") or [])


def index(rows: list[dict]) -> dict[tuple[str, int], str]:
    out = {}
    for row in rows:
        for key in ("content", "text", "chunk_text", "body"):
            if key in row:
                out[(row["doc_id"], int(row["chunk_index"]))] = flat(row[key])
                break
    return out


def around(text: str, needle: str) -> str:
    """The needle with context, so a person can see what the chunk is about."""
    pos = text.lower().find(needle.lower())
    if pos < 0:
        return text[:WINDOW] + (" ..." if len(text) > WINDOW else "")
    start = max(0, pos - WINDOW // 2)
    end = min(len(text), pos + len(needle) + WINDOW // 2)
    return (("... " if start else "") + text[start:pos]
            + "**" + text[pos:pos + len(needle)] + "**"
            + text[pos + len(needle):end] + (" ..." if end < len(text) else ""))


def main() -> int:
    import yaml

    for path in (FIXTURE, CORPUS, QUESTIONS):
        if not path.is_file():
            raise SystemExit(f"{path} not found")

    fixture, corpus = index(rows_of(FIXTURE)), index(rows_of(CORPUS))
    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    by_doc: dict[str, list[int]] = {}
    for doc, idx in corpus:
        by_doc.setdefault(doc, []).append(idx)

    broken = []
    for q in questions:
        if not q.get("answerable"):
            continue
        for g in (q.get("gold_chunks") or []):
            anchor = g.get("contains")
            if not anchor:
                continue
            key = (g["doc_id"], int(g["chunk_index"]))
            if key in corpus and flat(anchor).lower() in corpus[key].lower():
                continue
            broken.append((q, g, key, anchor))

    lines = [
        "# Relabelling review",
        "",
        f"{len(broken)} labels no longer hold against `data/chunks.json`. For each,",
        "the text the label was written against is shown first, recovered from",
        "`tests/fixture_corpus.json`, and then every chunk of the same document in",
        "the corpus on disk that contains the anchor.",
        "",
        "**Nothing is applied from this file until a decision line is filled in.**",
        "An automatic rule that moved each label to its nearest match would inflate",
        "every figure in the project, which is the failure `src/check_neighbours.py`",
        "already refused to commit and `docs/measurement-honesty.md` documents.",
        "",
        "Write the chosen index after `Decision:`, or `discard` if the label should",
        "go, or `read` if the chunk has to be opened before deciding. `CERTAIN`",
        "means the candidate's text is identical to the release chunk once",
        "whitespace is flattened, so only the index changed.",
        "",
        "---",
        "",
    ]

    certain = unclear = 0
    for q, g, (doc, idx), anchor in broken:
        release = fixture.get((doc, idx))
        needle = flat(anchor)
        candidates = sorted(i for i in by_doc.get(doc, [])
                            if needle.lower() in corpus[(doc, i)].lower())

        lines += [f"## {q['id']} · {doc} · chunk {idx}", "",
                  f"**Question.** {flat(q.get('question', '') or '')}", "",
                  f"**Anchor.** `{anchor}`", ""]
        answer = flat(q.get("gold_answer") or "")
        if answer:
            lines += [f"**Labelled answer.** {answer[:300]}"
                      + (" ..." if len(answer) > 300 else ""), ""]

        if release is None:
            lines += ["**The release text is not in the fixture for this "
                      "position.** Decide by reading the filing.", ""]
        else:
            lines += ["**The release chunk, as labelled on 17 August:**", "",
                      "> " + around(release, anchor), ""]

        if not candidates:
            lines += ["**No candidate in the corpus on disk contains this "
                      "anchor.** That contradicts diagnose_labels.py and has to "
                      "be understood before anything is changed.", ""]
            unclear += 1
        else:
            lines += [f"**Candidates in the corpus on disk** "
                      f"({len(candidates)} chunk(s) contain the anchor):", ""]
            for i in candidates:
                same = release is not None and corpus[(doc, i)] == release
                if same:
                    certain += 1
                mark = "  **CERTAIN — identical to the release chunk**" if same else ""
                lines += [f"- **chunk {i}** ({i - idx:+d}){mark}", "",
                          "  > " + around(corpus[(doc, i)], anchor), ""]
            if not any(corpus[(doc, i)] == release for i in candidates):
                unclear += 1

        lines += ["**Decision:** ", "", "---", ""]

    lines += [
        "## Summary",
        "",
        f"- {len(broken)} labels to decide",
        f"- {certain} candidate(s) byte-identical to the release chunk",
        f"- {unclear} label(s) with no identical candidate, which need the filing"
        " opened",
        "",
        "When the decisions are written, `python apply_relabel.py` reads this file",
        "and changes only the labels with a decision. Then re-run",
        "`python src/verify_labels.py --questions eval/questions_vnext.yaml"
        " --max-anchor-matches 8 --max-exceptions 4`,",
        "rebuild the fixture with `python tests/fixture.py --build`, and re-measure",
        "retrieval. The published 0.735 was measured against the labels as they",
        "were; a new figure has to be published as a new figure.",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(broken)} labels to review, {certain} with an identical candidate")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")
    print("\nRead it, fill in the decision lines, and nothing else changes until\n"
          "you do. No figure has moved.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
