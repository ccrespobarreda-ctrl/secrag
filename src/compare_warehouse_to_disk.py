#!/usr/bin/env python3
"""
Where do the warehouse and the corpus on disk differ, and what changed there?

    python src/compare_warehouse_to_disk.py

WHY

The warehouse holds 4,169 chunks. `data/chunks.json`, written on 14 August, holds
4,124 -- and a clean clone in September, on `lxml` 6.1.3 and `beautifulsoup4`
4.15.0 against August's versions, produced 4,124 with byte-identical text. So the
pipeline is deterministic and the library versions are not the cause. Finding 17
says they are, and that has to be corrected.

What is left is that the warehouse was loaded before the re-parse of 14 August
and never reloaded. If so, the README's table attributes +0.029 Recall@16 to a
re-parse that changed files on disk and not what was measured -- and every
published figure comes from the corpus that preceded it.

This compares the two document by document and prints where they diverge. Read
only; it opens the warehouse and reads a JSON file, and writes nothing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISK = ROOT / "data" / "chunks.json"


def flat(text: str) -> str:
    return " ".join(str(text).split())


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set. Run `. .\\load-env.ps1` first.")
        return 2
    if not DISK.is_file():
        print(f"{DISK} not found.")
        return 2

    import psycopg2
    cur = psycopg2.connect(os.environ["DATABASE_URL"]).cursor()
    cur.execute("select doc_id, chunk_index, item_section, content from chunks")
    warehouse = {(d, int(i)): (sec, flat(c)) for d, i, sec, c in cur.fetchall()}

    raw = json.loads(DISK.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else (raw.get("chunks") or [])
    disk = {(r["doc_id"], int(r["chunk_index"])):
            (r.get("item_section"), flat(r["content"])) for r in rows}

    print(f"warehouse {len(warehouse)} chunks | disk {len(disk)} chunks")

    docs = sorted({d for d, _ in warehouse} | {d for d, _ in disk})
    print(f"\n{'document':<20}{'warehouse':>10}{'disk':>8}{'diff':>7}"
          f"   first index whose text differs")
    print("-" * 78)

    total_diff = 0
    for doc in docs:
        w = {i for d, i in warehouse if d == doc}
        k = {i for d, i in disk if d == doc}
        first = None
        for i in sorted(w & k):
            if warehouse[(doc, i)][1] != disk[(doc, i)][1]:
                first = i
                break
        total_diff += len(w) - len(k)
        mark = "" if len(w) == len(k) else "  <--"
        print(f"{doc:<20}{len(w):>10}{len(k):>8}{len(w) - len(k):>7}"
              f"   {first if first is not None else 'none':<8}{mark}")

    print(f"\n{total_diff} chunks more in the warehouse than on disk")

    # Section labels are what the 14 August commit changed: "fronteras de
    # seccion y deteccion de compania (Gap)". If the warehouse assigns
    # different sections to the same positions, it predates that commit.
    both = sorted(set(warehouse) & set(disk))
    sec_diff = [(d, i, warehouse[(d, i)][0], disk[(d, i)][0])
                for d, i in both if warehouse[(d, i)][0] != disk[(d, i)][0]]
    print(f"\n{len(sec_diff)} of {len(both)} shared positions carry a different "
          f"item_section")
    for d, i, w, k in sec_diff[:10]:
        print(f"  {d:<20} {i:>4}   warehouse {str(w):<10} disk {k}")
    if len(sec_diff) > 10:
        print(f"  ... {len(sec_diff) - 10} more")

    print()
    if total_diff and sec_diff:
        print("The warehouse has more chunks AND assigns different sections to\n"
              "shared positions. It was parsed by different code, which is the\n"
              "re-parse of 14 August, and it was never reloaded afterwards.\n"
              "Every published figure was measured over the corpus that\n"
              "preceded that commit.")
    elif total_diff:
        print("More chunks in the warehouse, same sections where they overlap.\n"
              "The difference is in chunking rather than section boundaries.")
    else:
        print("Same size. The 4,169 count came from somewhere other than a\n"
              "different parse, and that has to be found before anything else.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
