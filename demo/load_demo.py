#!/usr/bin/env python3
"""
Load the demo corpus into the demo database.

    docker compose -f demo/docker-compose.yml up -d
    python demo/load_demo.py

No corpus download, no embedding run, no API key. 295 chunks of real 10-K text
with their vectors, from demo/demo_corpus.json.

WHY THIS IS NOT src/load.py

src/load.py loads the corpus: a chunks file, a manifest and a .npy of four
thousand vectors, none of which are in the repository. This reads one committed
JSON and writes the same two tables with the same columns.

IT REFUSES TO WRITE INTO A DATABASE THAT ALREADY HAS A CORPUS

The label fixture was once loaded on top of a database holding 4,169 chunks. The
loader upserts rather than truncates, so it reported success, and the check that
followed counted 4,124 chunks instead of 295 and looked entirely reasonable.
Nothing errored.

A demo aimed at someone who has never seen this repository is exactly where that
happens again, so the count is checked before anything is written, and a
database with unexpected content is a refusal rather than a merge.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

log = logging.getLogger("demo-load")

CORPUS = ROOT / "demo" / "demo_corpus.json"
SCHEMA = ROOT / "sql" / "schema.sql"
DEMO_URL = "postgresql://secrag:secrag@localhost:5434/secrag_demo"


def main() -> int:
    ap = argparse.ArgumentParser(description="Load the self-contained demo corpus")
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL")
                    or DEMO_URL,
                    help=f"defaults to DATABASE_URL, or {DEMO_URL}")
    ap.add_argument("--force", action="store_true",
                    help="load even if the database already holds chunks")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.corpus.exists():
        log.error("%s not found.", args.corpus)
        log.error("A maintainer builds it once: python demo/build_demo_corpus.py")
        return 2

    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    docs, chunks = data["documents"], data["chunks"]

    import psycopg2
    try:
        conn = psycopg2.connect(args.database_url)
    except Exception as exc:
        log.error("Could not connect to %s", args.database_url)
        log.error("  %s", str(exc).strip().splitlines()[0])
        log.error("Is the demo database up?")
        log.error("  docker compose -f demo/docker-compose.yml up -d")
        return 2

    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(open(SCHEMA, encoding="utf-8").read())

    cur.execute("select count(*) from chunks")
    existing = cur.fetchone()[0]
    if existing and not args.force:
        log.error("This database already holds %s chunks.", f"{existing:,}")
        log.error("Loading on top of them would succeed and leave a corpus that "
                  "is neither\nthe demo nor whatever was there before, which is "
                  "a mistake this project\nhas already made once and did not "
                  "notice for a day.")
        log.error("")
        log.error("If it is the demo database, empty it:")
        log.error("  docker compose -f demo/docker-compose.yml down -v")
        log.error("  docker compose -f demo/docker-compose.yml up -d")
        log.error("If you meant this one, pass --force.")
        conn.close()
        return 1

    for d in docs:
        cur.execute("""
            insert into documents (doc_id, ticker, company, cik, form_type,
                                   fiscal_year, filed_date, source_url,
                                   raw_chars)
            values (%(doc_id)s, %(ticker)s, %(company)s, %(cik)s,
                    %(form_type)s, %(fiscal_year)s, %(filed_date)s,
                    %(source_url)s, %(raw_chars)s)
            on conflict (doc_id) do nothing""", d)

    for c in chunks:
        cur.execute("""
            insert into chunks (doc_id, item_section, section_title,
                                chunk_index, token_count, content, embedding)
            values (%(doc_id)s, %(item_section)s, %(section_title)s,
                    %(chunk_index)s, %(token_count)s, %(content)s,
                    %(embedding)s)
            on conflict (doc_id, chunk_index) do update set
                content = excluded.content,
                embedding = excluded.embedding""",
            dict(c, embedding="[" + ",".join(str(x) for x in c["embedding"]) + "]"))

    cur.execute("select count(*) from chunks where embedding is null")
    n_null = cur.fetchone()[0]
    cur.execute("select count(*) from chunks")
    n_chunks = cur.fetchone()[0]
    conn.close()

    if n_chunks != len(chunks) or n_null:
        log.error("%d chunks loaded of %d, %d without a vector",
                  n_chunks, len(chunks), n_null)
        return 1

    log.info("%d documents and %d chunks, all with vectors", len(docs), n_chunks)
    log.info("")
    log.info("Ask it something, no API key needed:")
    log.info('  $env:DATABASE_URL = "%s"', args.database_url)
    log.info('  $env:LLM_PROVIDER = "echo"')
    log.info('  python src/search.py "contract manufacturers footwear"')
    log.info("")
    log.info("demo/README.md has questions this extract can answer, and says "
             "why most\nothers are correctly refused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
