#!/usr/bin/env python3
"""
Which corpus is in the warehouse, and did anything write into it that should not have?

    python src/inspect_warehouse.py

WHY

On 9 September `pin_corpus.py --verify` reported 4,169 chunks where 4,124 were
declared, and `verify_labels.py` failed 20 of 62 labels -- the same labels
repaired the day before, failing at their new positions because the old ones are
correct in this corpus. Two gates disagreeing with the disk from opposite sides.

Two explanations, and they call for opposite responses:

  the warehouse holds the release corpus
      Then the 4,169-chunk corpus was never lost. It has been in Postgres since
      August, and the three searches that concluded otherwise on 8 September --
      verify_release, find_release_commit, find_release_blobs -- all looked at
      files and none looked at the database. That is a correction to the README,
      not just to a run.

  something wrote into it
      `tests/fixture.py --load` inserts into `chunks` with
      `on conflict do update set content = excluded.content`. It was run on
      8 September against DATABASE_URL. A test tool writing into the working
      warehouse would be a defect of its own, and the 295 rows it inserts carry
      no embedding, which is how to tell.

Read-only. Nothing here writes, and the answer decides what gets measured next.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PROBES = [
    # (doc_id, chunk_index, what should be there, which corpus says so)
    ("URBN-10-K-2026", 121, "6,165,376", "release, 4,169 chunks"),
    ("URBN-10-K-2026", 118, "6,165,376", "current, 4,124 chunks"),
    ("LULU-10-K-2026", 100, "1,700,753", "release, 4,169 chunks"),
    ("LULU-10-K-2026", 96, "1,700,753", "current, 4,124 chunks"),
    ("CROX-10-K-2025", 169, "Deloitte", "release, 4,169 chunks"),
    ("CROX-10-K-2025", 166, "Deloitte", "current, 4,124 chunks"),
]


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set. Run `. .\\load-env.ps1` first.")
        return 2

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select count(*) from chunks")
    total = cur.fetchone()[0]
    cur.execute("select count(*) from documents")
    docs = cur.fetchone()[0]
    print(f"{total} chunks in {docs} documents")

    # A chunk with no vector was not written by src/load.py, which requires an
    # embeddings file. tests/fixture.py --load leaves embedding null.
    cur.execute("select count(*) from chunks where embedding is null")
    no_vector = cur.fetchone()[0]
    print(f"{no_vector} chunk(s) with no embedding")
    if no_vector:
        cur.execute("""select doc_id, count(*) from chunks
                       where embedding is null group by doc_id
                       order by count(*) desc limit 8""")
        for doc, n in cur.fetchall():
            print(f"    {doc:<20} {n}")
        print("  Rows with no vector were not written by src/load.py, which\n"
              "  needs an embeddings file. tests/fixture.py --load leaves them\n"
              "  null, and it was run against this database on 8 September.")

    print("\nWhere the labelled figures actually sit:")
    release = current = 0
    for doc, idx, needle, which in PROBES:
        cur.execute("""select content from chunks
                       where doc_id = %s and chunk_index = %s""", (doc, idx))
        row = cur.fetchone()
        if row is None:
            print(f"  {doc:<18} {idx:>4}  chunk absent")
            continue
        flat = " ".join(row[0].split()).lower()
        found = needle.lower() in flat
        if found:
            release += which.startswith("release")
            current += which.startswith("current")
        print(f"  {doc:<18} {idx:>4}  {needle:<28} "
              f"{'HERE' if found else 'not here':<9} ({which})")

    print()
    if release and not current:
        print("The warehouse holds the RELEASE corpus, 4,169 chunks.\n"
              "\n"
              "It was never lost. The three searches on 8 September looked at\n"
              "files and blobs and none of them looked in Postgres, so the\n"
              "README's claim that the release corpus cannot be rebuilt is\n"
              "wrong and has to be corrected.\n"
              "\n"
              "The 23 labels were repaired for the 4,124-chunk corpus and are\n"
              "correct for it. They are wrong for this one. Nothing should be\n"
              "measured until it is decided which corpus the project keeps.")
    elif current and not release:
        print("The warehouse holds the CURRENT corpus, 4,124 chunks, and the\n"
              "count of 4,169 came from somewhere else -- most likely rows\n"
              "inserted on top. The count above and the missing embeddings say\n"
              "which.")
    else:
        print("Mixed: figures from both corpora resolve. Something was loaded\n"
              "on top of something else, and this warehouse is not a corpus.\n"
              "It has to be rebuilt before anything is measured:\n"
              "  make reset-db && python src/load.py")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
