"""
What a measurement was measured against, recorded inside the measurement.

    import provenance as P
    payload = {"measured_against": P.describe(args.questions, cur), ...}

WHY THIS EXISTS

Two retrieval figures in this repository, 0.735 and 0.912, differ by almost
eighteen points and neither result file says which question file produced it,
how many labels that file held, or how many chunks were in the corpus. Working
that out took an afternoon of reading commit dates, hashing blobs and comparing
YAML files, and the answer was that one used `eval/questions.yaml` with 88
pre-canonical labels and the other the canonical 62. Every fact needed to tell
them apart existed at the moment of measuring and none of it was written down.

Findings 15 and 16 are both consequences: a corpus that stopped reproducing, and
a default argument pointing at abandoned labels. Neither could have survived a
result file that named its inputs.

WHAT IS RECORDED, AND WHY EACH

  questions_file    the path as given, because the default is not obvious and
                    `make sabotage` never passes one
  questions_sha256  the decisive field. Two runs of the same file are
                    comparable by construction; two runs of different files can
                    no longer be mistaken for each other
  n_questions       the shape of the sample the figure describes
  n_labels          with and without an anchor, because a label checked by
                    position only is finding 7 waiting to happen
  n_chunks          4,169 or 4,124 tells you which corpus, and that is the whole
                    of finding 15
  n_documents       19 or fewer: a filing that failed to download changes the
                    denominator silently
  splits            which of the three splits the measured questions belong to.
                    The README reports retrieval on the original 50 "and never
                    as a single average across splits, for the reason in
                    finding 1": the questions added later score 0.929 with a
                    bare keyword search against 0.412 for the ones written
                    first. A run over the master file mixes them, and the
                    resulting figure is not comparable with anything published.
                    Recorded rather than warned about, because a warning
                    scrolls past and a field does not

None of it is derived or estimated. If the database is unavailable the corpus
fields say so rather than guessing, because a missing fact recorded as missing
is worth more than a plausible one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

try:                                        # available in every harness
    import yaml
except ImportError:                         # pragma: no cover
    yaml = None


def _labels(path: Path) -> dict:
    if yaml is None:
        return {"n_questions": None, "n_labels": None,
                "n_labels_with_anchor": None, "note": "pyyaml unavailable"}
    try:
        questions = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except OSError as exc:
        return {"note": f"question file unreadable: {exc}"}

    labels = [g for q in questions if q.get("answerable")
              for g in (q.get("gold_chunks") or [])]
    return {
        "n_questions": len(questions),
        "n_answerable": sum(1 for q in questions if q.get("answerable")),
        "n_labels": len(labels),
        "n_labels_with_anchor": sum(1 for g in labels if g.get("contains")),
    }


def _splits(questions) -> dict:
    """Which splits the measured questions come from, by their ids."""
    root = Path(__file__).resolve().parent.parent
    path = root / "eval" / "vnext_splits.yaml"
    if yaml is None or not path.is_file():
        return {}
    try:
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}

    member = {}
    for name, ids in spec.items():
        if isinstance(ids, list):
            for qid in ids:
                member[str(qid)] = name

    seen = {}
    for q in questions:
        seen.setdefault(member.get(str(q.get("id")), "unassigned"), 0)
        seen[member.get(str(q.get("id")), "unassigned")] += 1

    out = {"splits": dict(sorted(seen.items()))}
    if len(seen) > 1:
        out["splits_note"] = (
            "More than one split. A single average across splits is not "
            "comparable with the published retrieval figure, which is reported "
            "on the original 50 questions only, for the reason in finding 1."
        )
    return out


def preserve(path) -> Path | None:
    """Move an existing result file aside instead of overwriting it.

    On 8 September a free `--provider echo` smoke run overwrote
    eval/results/correctness.json with 0% correct and 94% judge errors. The file
    was not tracked, so nothing was lost, and the next one would have been.

    A --force flag would have been the obvious answer and the wrong one: a flag
    that has to be passed on every legitimate re-run gets passed reflexively,
    and then it is not a guard. Moving the old file costs nothing, needs no
    argument, and keeps the evidence.
    """
    path = Path(path)
    if not path.exists():
        return None
    prev = path.with_name(f"{path.stem}.prev{path.suffix}")
    path.replace(prev)
    return prev


def _corpus(cur) -> dict:
    """Chunk and document counts, or an honest absence."""
    if cur is None:
        return {"n_chunks": None, "n_documents": None,
                "note": "no database connection at write time"}
    try:
        cur.execute("select count(*) from chunks")
        chunks = cur.fetchone()[0]
        cur.execute("select count(*) from documents")
        docs = cur.fetchone()[0]
        return {"n_chunks": chunks, "n_documents": docs}
    except Exception as exc:                # the shape of the error is the fact
        return {"n_chunks": None, "n_documents": None,
                "note": f"corpus counts unavailable: {type(exc).__name__}"}


def file_digest(path) -> dict:
    """Path, hash and size of an input that is not the question file.

    evaluate_correctness.py judges the answers in a generation result file and
    records nothing about which one. The manifest's correctness figures came
    from `correctness_final_rrf40_run0.json`, and which generation run produced
    the answers it judged is not written anywhere.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"path": path.as_posix(), "sha256": None,
                "note": f"unreadable: {exc}"}
    return {"path": path.as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data)}


def describe(questions_path, cur=None) -> dict:
    path = Path(questions_path)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        digest = None

    block = {
        "questions_file": path.as_posix(),
        "questions_sha256": digest,
        **_labels(path),
        **_corpus(cur),
    }
    if yaml is not None:
        try:
            block.update(_splits(yaml.safe_load(
                path.read_text(encoding="utf-8")) or []))
        except OSError:
            pass
    return block


def summarise(block: dict) -> str:
    """One line for a log, so the fact is visible at run time too."""
    short = (block.get("questions_sha256") or "unknown")[:12]
    return (f"measured against {block.get('questions_file')} "
            f"[{short}] — {block.get('n_labels')} labels "
            f"({block.get('n_labels_with_anchor')} anchored) over "
            f"{block.get('n_chunks')} chunks in "
            f"{block.get('n_documents')} documents")
