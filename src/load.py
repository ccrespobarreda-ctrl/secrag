#!/usr/bin/env python3
"""
Load documents, chunks and vectors into Postgres.

    python src/load.py

Indexes are created after the rows, not before. Inserting into an existing HNSW
index is markedly slower, and the index built afterwards is no different.

The load reconciles at the end. A load that reports success while dropping 3% of
rows looks identical to one that worked, so the counts are compared against the
files on disk rather than trusted.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("load")


def doc_id_from(entry: dict) -> str:
    """
    The identifier that joins a manifest entry to its chunks.

    src/chunk.py derives doc_id from the stem of the parsed JSON filename, which
    is always clean. This side derived it from manifest["local_path"], and that
    path carries whatever separator the machine that wrote it uses:

        'data\\raw\\NKE-10-K-2026.html'

    On Windows Path().stem gives 'NKE-10-K-2026'. On Linux the backslash is an
    ordinary character, so the stem is the entire string and every chunk then
    references a doc_id that does not exist -- a foreign key violation on the
    first insert, with nothing pointing at the manifest as the cause. The project
    ran only on the machine that produced the manifest.

    Newer manifests carry doc_id explicitly. Older ones are handled by splitting
    on both separators, so an existing data/manifest.json still loads.
    """
    if entry.get("doc_id"):
        return entry["doc_id"]

    raw = str(entry["local_path"]).replace("\\", "/")
    return PurePosixPath(raw).stem


INDEX_SQL = [
    ("chunks_embedding_idx",
     "create index if not exists chunks_embedding_idx on chunks "
     "using hnsw (embedding vector_cosine_ops)"),
    ("chunks_tsv_idx",
     "create index if not exists chunks_tsv_idx on chunks using gin (content_tsv)"),
    ("chunks_section_idx",
     "create index if not exists chunks_section_idx on chunks (doc_id, item_section)"),
]


def load_documents(cur, manifest: list[dict]) -> int:
    rows = []
    for f in manifest:
        doc_id = doc_id_from(f)
        missing = [k for k in ("source_url", "fiscal_year", "filed_date")
                   if not f.get(k)]
        if missing:
            raise SystemExit(
                f"{doc_id} is missing {', '.join(missing)} in the manifest. "
                f"Delete data/manifest.json and re-run src/edgar.py.")
        rows.append((doc_id, f["ticker"], f["company"], f["cik"], f["form_type"],
                     f["fiscal_year"], f["filed_date"], f["source_url"],
                     f["raw_chars"]))

    cur.executemany("""
        insert into documents
          (doc_id, ticker, company, cik, form_type, fiscal_year, filed_date,
           source_url, raw_chars)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (doc_id) do update set
          ticker = excluded.ticker, company = excluded.company,
          source_url = excluded.source_url, raw_chars = excluded.raw_chars
    """, rows)
    return len(rows)


def load_chunks(cur, chunks: list[dict], vectors, batch: int = 500) -> int:
    inserted = 0
    for start in range(0, len(chunks), batch):
        window = chunks[start:start + batch]
        rows = [
            (c["doc_id"], c["item_section"], c["section_title"], c["chunk_index"],
             c["token_count"], c["content"],
             "[" + ",".join(f"{x:.6f}" for x in vectors[start + i]) + "]")
            for i, c in enumerate(window)
        ]
        cur.executemany("""
            insert into chunks
              (doc_id, item_section, section_title, chunk_index, token_count,
               content, embedding)
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (doc_id, chunk_index) do update set
              content = excluded.content, embedding = excluded.embedding,
              token_count = excluded.token_count
        """, rows)
        inserted += len(rows)
        log.info("  %s / %s chunks", f"{inserted:,}", f"{len(chunks):,}")
    return inserted


def reconcile(cur, expected_docs: int, expected_chunks: int) -> list[str]:
    """Compare what is in the warehouse against what was on disk."""
    problems = []

    cur.execute("select count(*) from documents")
    n_docs = cur.fetchone()[0]
    if n_docs != expected_docs:
        problems.append(f"{n_docs} documents in the warehouse, {expected_docs} on disk")

    cur.execute("select count(*) from chunks")
    n_chunks = cur.fetchone()[0]
    if n_chunks != expected_chunks:
        problems.append(f"{n_chunks} chunks in the warehouse, {expected_chunks} on disk")

    cur.execute("select count(*) from chunks where embedding is null")
    n_null = cur.fetchone()[0]
    if n_null:
        problems.append(f"{n_null} chunks have no vector")

    # A chunk whose text produced no lexemes is invisible to keyword search. It
    # happens with fragments that are pure punctuation or numbers.
    cur.execute("select count(*) from chunks where content_tsv = ''::tsvector")
    n_empty = cur.fetchone()[0]
    if n_empty:
        problems.append(f"{n_empty} chunks produced an empty tsvector "
                        f"and cannot be found by keyword search")

    cur.execute("""
        select count(*) from chunks c
        left join documents d using (doc_id) where d.doc_id is null
    """)
    n_orphan = cur.fetchone()[0]
    if n_orphan:
        problems.append(f"{n_orphan} chunks reference a missing document")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Load the corpus into Postgres")
    ap.add_argument("--chunks", default="data/chunks.json", type=Path)
    ap.add_argument("--vectors", default="data/embeddings.npy", type=Path)
    ap.add_argument("--manifest", default="data/manifest.json", type=Path)
    ap.add_argument("--truncate", action="store_true",
                    help="empty the tables first; reissues every chunk_id")
    ap.add_argument("--dry-run", action="store_true",
                    help="reconcile what is already loaded, write nothing")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")

    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    for path in (args.chunks, args.vectors, args.manifest):
        if not path.exists():
            log.error("%s not found", path)
            return 2

    import numpy as np
    import psycopg2

    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    vectors = np.load(args.vectors)

    if len(vectors) != len(chunks):
        log.error("%d vectors for %d chunks — re-run src/embed.py",
                  len(vectors), len(chunks))
        return 1
    if vectors.shape[1] != C.EMBEDDING_DIM:
        log.error("vectors have %d dimensions, the column is vector(%d)",
                  vectors.shape[1], C.EMBEDDING_DIM)
        return 1

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    started = time.time()

    # Reconcile only. `make verify-load` has always called this flag; until now
    # it did not exist, so the target failed with an argparse error rather than
    # checking anything.
    if args.dry_run:
        problems = reconcile(cur, len(manifest), len(chunks))
        if problems:
            log.error("The warehouse does not match the files on disk:")
            for p in problems:
                log.error("  %s", p)
            conn.close()
            return 1
        log.info("%d documents and %s chunks on disk reconcile against the "
                 "warehouse; nothing was written", len(manifest),
                 f"{len(chunks):,}")
        conn.close()
        return 0

    if args.truncate:
        # restart identity is kept deliberately. The load is deterministic --
        # src/chunk.py walks the parsed files in sorted order, and the inserts
        # below follow that order -- so an unchanged chunks.json reproduces the
        # same chunk_ids, which is what lets the gold labels survive a reload.
        #
        # If chunking changed, they do not, and eval/questions.yaml then points
        # at different text with no error anywhere. Hence the warning and
        # src/verify_labels.py.
        log.warning("Emptying chunks and documents, and restarting chunk_id at 1")
        log.warning("  The 88 gold labels in %s are chunk_ids. They survive only "
                    "if chunks.json is unchanged.", C.EVAL_QUESTIONS)
        log.warning("  Run src/verify_labels.py after this load, before "
                    "trusting any retrieval metric.")
        cur.execute("truncate chunks, documents restart identity cascade")

    # Dropped before the insert and rebuilt after: maintaining HNSW row by row is
    # far slower than building it once over the finished table.
    log.info("Dropping indexes for the load")
    for name, _ in INDEX_SQL:
        cur.execute(f"drop index if exists {name}")

    n_docs = load_documents(cur, manifest)
    log.info("%d documents", n_docs)

    n_chunks = load_chunks(cur, chunks, vectors)
    conn.commit()

    log.info("Rebuilding indexes")
    for name, sql in INDEX_SQL:
        t0 = time.time()
        cur.execute(sql)
        conn.commit()
        log.info("  %-24s %.1fs", name, time.time() - t0)

    problems = reconcile(cur, len(manifest), len(chunks))
    log.info("Loaded in %.0fs", time.time() - started)

    if problems:
        log.error("Reconciliation failed:")
        for p in problems:
            log.error("  %s", p)
        conn.close()
        return 1

    cur.execute("""
        select item_section, count(*), round(avg(token_count)) 
        from chunks group by 1 order by 1
    """)
    log.info("  %-10s %8s %8s", "section", "chunks", "avg tok")
    for section, n, avg in cur.fetchall():
        log.info("  %-10s %8s %8d", section, f"{n:,}", avg)

    log.info("%d documents and %s chunks reconcile against the files on disk",
             n_docs, f"{n_chunks:,}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
