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

AND WHICH DATABASE, WHICH IS THE EASIER MISTAKE

The corpus is not in the repository and DATABASE_URL is not versioned, so which
database a run measures against is decided by a shell variable. Four databases
have answered to that variable in this project: the managed instance the figures
were measured on, a local container holding an older load, the label fixture, and
the demo. Three of them return a number and none of them raises anything.

A session once pointed at a 295-chunk extract and was one command away from
generating seventy questions against it, at a real cost, with output that would
have looked entirely ordinary. --expect-chunks turns that into a failure:

    python src/check_db_settings.py --expect-chunks 4169

Run it before anything that spends money or gets published. It is the same
argument as every other check here — a number measured against the wrong thing
is indistinguishable from a number measured against the right one.
"""

from __future__ import annotations

import argparse
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
    ap = argparse.ArgumentParser(
        description="Report the settings retrieval reproducibility depends on")
    ap.add_argument("--expect-chunks", type=int,
                    help="fail unless the database holds exactly this many "
                         "chunks. The published figures were measured on 4,169")
    args = ap.parse_args()

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

    # The host, with no credentials. Reading "localhost" where the published
    # figures came from a managed instance is the whole point of printing it.
    url = os.environ["DATABASE_URL"]
    host = url.split("@")[-1].split("/")[0] if "@" in url else "(no host)"
    print(f"\n  host   {host}")

    conn.close()
    print("\n  If ef_search is not the value the published figures were "
          "measured under,\n  changing it now produces different numbers "
          "against the same corpus.")

    if args.expect_chunks is not None and total != args.expect_chunks:
        print(f"\n{'=' * 66}")
        print(f"WRONG DATABASE: {total:,} chunks, expected "
              f"{args.expect_chunks:,}")
        print("=" * 66)
        print(f"  host  {host}")
        print(f"  name  {db}")
        print("\n  DATABASE_URL points somewhere other than the corpus the "
              "published\n  figures were measured on. Nothing here would have "
              "raised: retrieval\n  returns chunks, the harness prints a "
              "number, and the number is\n  measured against a different "
              "corpus.")
        print("\n  Fix the variable before running anything that spends money "
              "or gets\n  published. If this database is deliberate, it is a "
              "new measurement\n  and not comparable with anything already "
              "reported.")
        return 1

    if args.expect_chunks is not None:
        print(f"\n  {total:,} chunks, as expected. This is the corpus the "
              f"published figures\n  were measured on.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
