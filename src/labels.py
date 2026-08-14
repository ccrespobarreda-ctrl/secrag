#!/usr/bin/env python3
"""
Resolve gold labels against the corpus. One module, so the format is defined once.

    from labels import load, resolve
    questions = load(Path(C.EVAL_QUESTIONS))
    problems = resolve(cur, questions)      # fills q["gold_chunk_ids"]

WHAT CHANGED AND WHY

Labels used to be bare serial ids:

    gold_chunk_ids: [3236, 3294]

chunk_id comes from a bigserial. The number 3236 means "the answer to Q002" only
because someone read chunk 3236 on one particular afternoon, and three ordinary
actions reissue it to different text: sql/reset.sql, load.py --truncate, and any
change to chunking. None of them errors. Retrieval keeps returning chunks and the
harness keeps printing a number.

The failure is also global. chunk_id is assigned across the whole corpus in load
order, so re-parsing one filing shifts every id after it. Changing Wayfair
invalidated all 88 labels at once.

    gold_chunks:
      - {doc_id: UAA-10-K-2026, chunk_index: 212, contains: "4,966,370"}

Three fields, each doing one job:

  doc_id + chunk_index   Survives a reload, and confines the blast radius. Re-
                         parsing Wayfair now invalidates Wayfair's labels only.

  contains               Turns a silent failure into a loud one. If the label
                         still resolves but the text behind it moved, this is
                         what notices.

WHY NOT A HASH

A content hash breaks on a changed whitespace character, which is the most
common harmless difference between two chunkings. `contains` holds a figure or a
proper noun taken from the answer, so it survives any re-chunking that still
leaves the answer inside the chunk -- and fails exactly when it does not. That is
the property wanted, and a hash has the opposite one.

It is also the criterion already written in docs/labeling-guide, "could a reader
seeing only this chunk answer the question", moved somewhere a machine can check.
"""

from __future__ import annotations

import re
from pathlib import Path

# A figure with grouping, as filings write them: 6,165,376 / 12,601.5 / 4966370.
_FIGURE = re.compile(r"\d[\d,]{3,}(?:\.\d+)?")

# Short figures: "$7.5 billion", "45%", "May 31". Real anchors but weak ones: a
# filing writing 45.2% where the label rounded to 45% is a labeling imprecision,
# not a moved chunk, so a miss here asks for a human rather than declaring the
# label broken.
_SHORT_FIGURE = re.compile(
    r"\b\d+\.\d+\b"
    r"|\b\d+(?:\.\d+)?\s?%"
    r"|\b(?:January|February|March|April|May|June|July|August|September"
    r"|October|November|December)\s+\d{1,2}\b")

# A span quoted from the filing while labeling.
_QUOTED = re.compile(r"['\"]([^'\"]{8,})['\"]")

# Proper nouns: Capitalised or ALL-CAPS runs of four characters or more.
_PROPER = re.compile(r"\b(?:[A-Z][a-zA-Z]{3,}|[A-Z]{4,})\b")

# Capitalised for position or grammar rather than because they name anything,
# in both languages the labels are written in.
_NOT_A_NAME = {
    "Revenue", "Total", "Category", "Categories", "Categorias", "Ropa",
    "Suscripciones", "Note", "Notes", "Item", "Items", "Fiscal", "Year",
    "Company", "Reported", "Both", "Ambos", "Cada", "Este", "Esta", "Esto",
    "Segun", "Sobre", "Para", "Como", "Donde", "Cuando", "Porque",
    "Sales", "Income", "Statement", "Statements", "Million", "Billion",
    "Thousand", "Miles", "Millones", "Segmento", "Segmentos", "Ejercicio",
}


def anchors(gold_answer: str) -> list[str]:
    """
    Strings from the labeled answer that must survive in the labeled chunk.

    Most distinctive first, so a failure report leads with the figure rather
    than with a company name that appears on every page of the filing.
    """
    if not gold_answer:
        return []

    found: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        # Trailing punctuation comes along with the match: the figure pattern
        # reads "2025," out of "in fiscal 2025, revenues rose", and an anchor
        # carrying a comma fails against a chunk that writes the same figure at
        # the end of a sentence.
        value = value.strip().strip(" ,;:").rstrip(".")
        key = value.lower()
        if len(value) >= 4 and key not in seen:
            seen.add(key)
            found.append(value)

    for m in _FIGURE.findall(gold_answer):
        add(m)
    for m in _QUOTED.findall(gold_answer):
        # A long quote rarely survives verbatim; its opening clause does.
        add(" ".join(m.split()[:6]))
    for m in _PROPER.findall(gold_answer):
        if m not in _NOT_A_NAME:
            add(m)

    return found


def weak_anchors(gold_answer: str) -> list[str]:
    """Short figures, used only when the answer yields no strong anchor."""
    if not gold_answer:
        return []
    out, seen = [], set()
    for m in _SHORT_FIGURE.findall(gold_answer):
        m = m.strip().strip(" ,;:").rstrip(".")
        key = m.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(m)
    return out


def normalise(text: str) -> str:
    """Collapse whitespace, so a figure split across a line break still matches."""
    return " ".join(text.split()).lower()


def load(path: Path) -> list[dict]:
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []


def resolve(cur, questions: list[dict]) -> list[dict]:
    """
    Fill gold_chunk_ids on every question, from whichever format it uses.

    Mutates the questions in place and returns a list of problems. Callers decide
    what to do with them, but nothing downstream should treat an unresolved label
    as an absent one: a question whose label no longer resolves is not an
    unlabeled question, it is a broken measurement.
    """
    problems: list[dict] = []

    for q in questions:
        if not q.get("answerable"):
            q.setdefault("gold_chunk_ids", [])
            continue

        spec = q.get("gold_chunks")

        # Legacy format. Still resolved, so a half-migrated file runs, but
        # reported so it does not stay half-migrated by accident.
        if not spec:
            if q.get("gold_chunk_ids"):
                problems.append({
                    "id": q["id"], "kind": "legacy",
                    "detail": ("labeled with bare chunk_ids, which do not survive "
                               "a reparse — migrate with src/migrate_labels.py"),
                })
            else:
                q["gold_chunk_ids"] = []
            continue

        resolved: list[int] = []
        for entry in spec:
            doc_id = entry.get("doc_id")
            index = entry.get("chunk_index")
            cur.execute("""
                select chunk_id, content from chunks
                where doc_id = %s and chunk_index = %s
            """, (doc_id, index))
            row = cur.fetchone()

            if row is None:
                problems.append({
                    "id": q["id"], "kind": "missing",
                    "detail": f"{doc_id} has no chunk {index} — the filing was "
                              f"re-chunked into fewer pieces",
                })
                continue

            chunk_id, content = row
            needle = entry.get("contains")
            if needle and normalise(needle) not in normalise(content):
                problems.append({
                    "id": q["id"], "kind": "moved",
                    "detail": f"{doc_id} chunk {index} exists as chunk_id "
                              f"{chunk_id} but no longer contains {needle!r}",
                })
                continue

            resolved.append(chunk_id)

        q["gold_chunk_ids"] = resolved

    return problems
