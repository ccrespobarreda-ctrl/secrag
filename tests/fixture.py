#!/usr/bin/env python3
"""
The smallest corpus that makes the label check mean something.

    python tests/fixture.py --build          # from the live warehouse
    python tests/fixture.py --load           # into an empty database

WHY THIS EXISTS

Continuous integration ran `verify_labels.py` behind a condition that was never
true: the corpus is not in the repository, so the step reported "skipping the
label check" and the build went green anyway. The guarantee the README claims —
that a green build means the measurements can be trusted — was not being made.

WHAT IS IN IT, AND WHAT IS NOT

Every chunk a gold label points at, plus the chunk either side of it. Nothing
else. That is roughly three hundred of 4,169, and it is enough to verify all 127
labels rather than a sample, because labels resolve by document and index rather
than by serial id, so a sparse subset resolves exactly as the full corpus does.

The neighbours are there for a second reason: the boundary defect recorded as
finding 8 — a risk factor split from its own content — is only visible with the
adjacent chunk present, and a finding nobody can reproduce is an assertion.

Chunks are stored whole. Truncating them would have halved the size and broken
the anchors that matter most: Crocs' gross profit sits at the end of a chunk
that opens with three hundred tokens of audit procedure.

WHY NOT src/load.py

That loader also requires an embeddings file, and three hundred vectors of 384
dimensions would add half a megabyte of numbers that verify nothing. Retrieval
is not what this fixture tests. The insert below writes the same two tables with
the same columns, leaving `embedding` null.

WHY IT RECORDS THE HASH OF THE QUESTION FILE

This fixture is derived from the labels, so the two move together or they
describe different corpora. On 8 and 10 September they came apart three times
and the build went red each time -- which was the good case. The bad case
happened once and went green: a fixture rebuilt against the wrong warehouse
agrees with the labels perfectly and describes a corpus the project does not
use. Nothing could tell the two apart, because `--check` only ever compared the
fixture against the questions, and a fixture built from those questions cannot
disagree with them.

So the build records the SHA-256 of the question file, and `--check` fails when
it no longer matches. That does not prove the fixture came from the right
warehouse -- `src/pin_corpus.py --verify` is what says which corpus is on the
other end of DATABASE_URL -- but it does prove the two files were made from the
same labels, which is the pair that kept drifting.

ON PUBLISHING FILING TEXT

The repository deliberately does not redistribute the corpus; `src/edgar.py`
fetches it. This is the minimum extract needed to reproduce a published check,
which is a different thing from republishing nineteen annual reports, and it is
described as such in the README rather than left for a reader to notice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

FIXTURE = ROOT / "tests" / "fixture_corpus.json"
log = logging.getLogger("fixture")


def questions_digest(path: Path) -> str:
    """Of the bytes, normalised to LF, not of the parsed YAML.

    The bytes, because a reordered file is a changed file and YAML would not
    notice. Normalised, because .gitattributes stores text with LF and checks it
    out per platform: the same file hashes one way on Windows and another on a
    Linux runner, and the first version of this check did neither -- it recorded
    the CRLF digest, continuous integration computed the LF one, and the gate
    written to catch a corpus mismatch failed the build over a line ending.

    That is finding 14 committed inside the fix for finding 19, with the lesson
    two days old. verify_release.py had already solved it the other way round,
    by restoring CR before hashing; here LF is the right direction, because this
    digest describes a file in the repository rather than bytes that were
    published.
    """
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build(cur, questions_path: Path, neighbours: int) -> dict:
    import labels as L

    questions = L.load(questions_path)
    L.resolve(cur, questions)

    wanted: set[tuple[str, int]] = set()
    for q in questions:
        for g in (q.get("gold_chunks") or []):
            doc, idx = g["doc_id"], g["chunk_index"]
            for d in range(-neighbours, neighbours + 1):
                if idx + d >= 0:
                    wanted.add((doc, idx + d))

    docs = sorted({d for d, _ in wanted})
    cur.execute("""select doc_id, ticker, company, cik, form_type, fiscal_year,
                          filed_date, source_url, raw_chars
                   from documents where doc_id = any(%s) order by doc_id""",
                (docs,))
    documents = [{"doc_id": r[0], "ticker": r[1], "company": r[2], "cik": r[3],
                  "form_type": r[4], "fiscal_year": r[5],
                  "filed_date": str(r[6]), "source_url": r[7],
                  "raw_chars": r[8]} for r in cur.fetchall()]

    chunks = []
    for doc in docs:
        idxs = sorted(i for d, i in wanted if d == doc)
        cur.execute("""select doc_id, item_section, section_title, chunk_index,
                              token_count, content
                       from chunks
                       where doc_id = %s and chunk_index = any(%s)
                       order by chunk_index""", (doc, idxs))
        for r in cur.fetchall():
            chunks.append({"doc_id": r[0], "item_section": r[1],
                           "section_title": r[2], "chunk_index": r[3],
                           "token_count": r[4], "content": r[5]})

    return {
        "note": ("Minimum corpus extract for the label check. Every chunk a "
                 "gold label points at, plus its immediate neighbours. Built by "
                 "tests/fixture.py --build; not a substitute for the corpus, "
                 "which src/edgar.py fetches."),
        "questions_file": questions_path.name,
        "questions_sha256": questions_digest(questions_path),
        "neighbours": neighbours,
        "documents": documents,
        "chunks": chunks,
    }


def check(data: dict, questions_path: Path) -> int:
    """
    Confirm the fixture can answer the question the label check asks, without a
    database.

    Loading a fixture into Postgres to find out it is incomplete is a slow way
    to learn it, and on a machine without Docker or psql it is no way at all.
    Every label resolves by document and index, and every anchor is a substring
    of the chunk it names; both are decidable from the file itself.

    This runs in continuous integration too, before the database step. A fixture
    that fails here would fail there for the same reason and take two minutes
    longer to say so.
    """
    import yaml

    # Before anything else. A fixture built from different labels can still
    # pass every check below -- that is what makes this the first one.
    recorded = data.get("questions_sha256")
    current = questions_digest(questions_path)
    if recorded is None:
        print("This fixture predates the hash check and cannot be matched to a\n"
              "question file. Rebuild it:  python tests/fixture.py --build\n")
    elif recorded != current:
        print(f"{questions_path.name} is not the file this fixture was built "
              f"from.\n"
              f"  fixture built from  {recorded[:16]}\n"
              f"  file on disk        {current[:16]}\n\n"
              f"One of the two moved. The labels and the fixture describe the "
              f"same corpus\nor they describe none, so rebuild against the "
              f"warehouse the labels belong to:\n"
              f"  python src/pin_corpus.py --verify\n"
              f"  python tests/fixture.py --build\n")
        return 1

    questions = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
    have = {(c["doc_id"], c["chunk_index"]): c["content"]
            for c in data["chunks"]}
    docs = {d["doc_id"] for d in data["documents"]}

    missing_chunk, missing_doc, missing_anchor = [], [], []
    n_labels = 0

    for q in questions:
        if not q.get("answerable"):
            continue
        for g in (q.get("gold_chunks") or []):
            n_labels += 1
            key = (g["doc_id"], g["chunk_index"])
            if g["doc_id"] not in docs:
                missing_doc.append((q["id"], g["doc_id"]))
            elif key not in have:
                missing_chunk.append((q["id"], *key))
            else:
                anchor = g.get("contains")
                if anchor:
                    flat = " ".join(have[key].split()).lower()
                    if " ".join(anchor.split()).lower() not in flat:
                        missing_anchor.append((q["id"], *key, anchor))

    print(f"{n_labels} labels against {len(have)} chunks in "
          f"{len(docs)} documents\n")
    for label, rows in (("document absent from the fixture", missing_doc),
                        ("chunk absent from the fixture", missing_chunk),
                        ("anchor not inside its chunk", missing_anchor)):
        print(f"  {label:<36}{len(rows):>4}")
        for r in rows[:6]:
            print(f"      {r}")
        if len(rows) > 6:
            print(f"      ... {len(rows) - 6} more")

    bad = len(missing_doc) + len(missing_chunk) + len(missing_anchor)
    if bad:
        print(f"\n{bad} label(s) the fixture cannot support. Rebuild it:\n"
              f"  python tests/fixture.py --build")
        return 1
    print("\nEvery label resolves inside the fixture and every anchor is "
          "present.\nThe database check will agree.")
    return 0


def load(cur, data: dict) -> tuple[int, int]:
    for d in data["documents"]:
        cur.execute("""
            insert into documents (doc_id, ticker, company, cik, form_type,
                                   fiscal_year, filed_date, source_url,
                                   raw_chars)
            values (%(doc_id)s, %(ticker)s, %(company)s, %(cik)s,
                    %(form_type)s, %(fiscal_year)s, %(filed_date)s,
                    %(source_url)s, %(raw_chars)s)
            on conflict (doc_id) do nothing""", d)

    for c in data["chunks"]:
        cur.execute("""
            insert into chunks (doc_id, item_section, section_title,
                                chunk_index, token_count, content)
            values (%(doc_id)s, %(item_section)s, %(section_title)s,
                    %(chunk_index)s, %(token_count)s, %(content)s)
            on conflict (doc_id, chunk_index) do update set
                content = excluded.content""", c)

    return len(data["documents"]), len(data["chunks"])


def main() -> int:
    ap = argparse.ArgumentParser(description="Corpus fixture for the label check")
    ap.add_argument("--build", action="store_true",
                    help="extract from the live warehouse")
    ap.add_argument("--load", action="store_true",
                    help="insert into the database in DATABASE_URL")
    ap.add_argument("--check", action="store_true",
                    help="validate the fixture against the questions, no "
                         "database needed")
    ap.add_argument("--questions", type=Path,
                    default=ROOT / "eval" / "questions_vnext.yaml")
    ap.add_argument("--neighbours", type=int, default=1)
    ap.add_argument("--out", type=Path, default=FIXTURE)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not (args.build or args.load or args.check):
        ap.error("give --build, --load or --check")

    if args.check:
        if not args.out.exists():
            print(f"{args.out} not found. Build it first.")
            return 1
        return check(json.loads(args.out.read_text(encoding="utf-8")),
                     args.questions)

    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    cur = conn.cursor()

    try:
        if args.build:
            data = build(cur, args.questions, args.neighbours)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(data, indent=1, ensure_ascii=False),
                                encoding="utf-8")
            size = args.out.stat().st_size / 1024
            print(f"{len(data['documents'])} documents, "
                  f"{len(data['chunks'])} chunks")
            print(f"wrote {args.out}  ({size:.0f} KB)")
            print("\nThis is the minimum extract for the label check, not the "
                  "corpus.\nRebuild it whenever the labels change:  "
                  "python tests/fixture.py --build")
        else:
            if not args.out.exists():
                print(f"{args.out} not found. Build it first.")
                return 1
            data = json.loads(args.out.read_text(encoding="utf-8"))
            n_docs, n_chunks = load(cur, data)
            print(f"loaded {n_docs} documents and {n_chunks} chunks")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
