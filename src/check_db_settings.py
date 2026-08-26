#!/usr/bin/env python3
"""
Report the database settings that decide whether retrieval is reproducible.

    python src/check_db_settings.py

WHY THIS EXISTS

Approximate nearest-neighbour search is approximate. pgvector's HNSW index reads
`hnsw.ef_search` to decide how wide to search, and the default of 40 trades
recall for speed. The value is a session or database setting, not part of the
index, so two runs of the same evaluation against the same corpus can return
different neighbours if it was changed in between — and nothing in the harness
would notice.

Every published retrieval figure was measured under whatever value was in force
at the time. Changing it later is not a tuning knob, it is a new measurement.
This prints the current value so that fact is visible rather than assumed.
"""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("db")

SETTINGS = [
    ("hnsw.ef_search", "how wide HNSW searches; higher is more accurate and "
                       "slower. pgvector default is 40."),
    ("hnsw.iterative_scan", "whether HNSW keeps scanning past the first pass."),
    ("ivfflat.probes", "unused here; listed so a change is visible."),
    ("default_text_search_config",
     "the server default. This project never relies on it: both the index and "
     "the queries name 'english' explicitly, which is why Neon defaulting to "
     "'simple' does not silently disable stemming."),
    ("server_version", "the Postgres build."),
]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    # pgvector registers its settings when the library loads into the session,
    # and that only happens once a vector type is touched. Querying SHOW on a
    # fresh connection reports "not set" for a value that is perfectly well
    # defined — a false negative produced by asking too early.
    try:
        cur.execute("select '[1,0]'::vector <-> '[0,1]'::vector")
        cur.fetchone()
    except Exception:
        conn.rollback()

    cur.execute("select current_database(), version()")
    db, version = cur.fetchone()
    print(f"database   {db}")
    print(f"server     {version.split(',')[0]}\n")

    for name, why in SETTINGS:
        try:
            cur.execute(f"show {name}")
            value = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            value = "not set on this server"
        print(f"  {name:<28}{value}")
        print(f"  {'':<28}{why}\n")

    cur.execute("""select count(*) from chunks where embedding is not null""")
    embedded = cur.fetchone()[0]
    cur.execute("select count(*) from chunks")
    total = cur.fetchone()[0]
    print(f"  chunks {embedded:,} embedded of {total:,}")

    cur.execute("""select indexname, indexdef from pg_indexes
                   where tablename = 'chunks' order by indexname""")
    print("\n  indexes on chunks")
    for name, definition in cur.fetchall():
        kind = ("hnsw" if "hnsw" in definition else
                "gin" if "gin" in definition else "btree")
        print(f"    {name:<28}{kind}")

    conn.close()
    print("\n  If ef_search is not the value the published figures were "
          "measured under,\n  changing it now produces different numbers "
          "against the same corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
