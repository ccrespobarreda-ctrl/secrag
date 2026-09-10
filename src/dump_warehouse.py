#!/usr/bin/env python3
"""
Copy the corpus out of the warehouse, in the format src/load.py reads back.

    python src/dump_warehouse.py --out data/warehouse_dump_20260910
    python src/load.py --chunks  data/warehouse_dump_20260910/chunks.json \\
                       --vectors data/warehouse_dump_20260910/embeddings.npy \\
                       --manifest data/warehouse_dump_20260910/manifest.json \\
                       --dry-run

WHY THIS EXISTS, AND WHY IT RUNS BEFORE THE RELOAD

The warehouse holds 4,169 chunks: the corpus every published figure was measured
over. `data/chunks.json` holds 4,124 and `data/embeddings.npy` holds 4,124
vectors that pair with it, so the 4,169 vectors exist in Postgres and in no
file anywhere. Reloading the warehouse -- which is what a new evaluation version
requires -- destroys them.

The tempting shortcut was to skip this and rebuild that corpus later from the
`src/parse.py` that preceded commit 4001782. That is a hypothesis: nobody has
checked that the old parser reproduces those 4,169 chunks. Betting the only copy
of a measured corpus on an unverified reconstruction is the wrong order. Dump
first; test the reconstruction against the dump afterwards, when being wrong
costs nothing.

If the reconstruction turns out to work, this dump becomes unnecessary and can
be deleted, and the project gains a stronger claim than a backup: that the
release corpus is rebuildable from immutable filings and committed code.

WHAT IT WRITES

  chunks.json      the same fields src/chunk.py emits, so load.py reads it
  embeddings.npy   float32, one row per chunk, in chunks.json order
  manifest.json    copied from data/manifest.json, unchanged
  MANIFEST.md      what this is, when, from where, and the hashes

The row order matters and is asserted: load.py pairs vector i with chunk i, and
a dump whose orders disagree would load a corpus where every chunk carries
somebody else's vector -- retrieval would still work, and every figure would be
quietly wrong. That check is the reason this is a script and not two queries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FIELDS = ("doc_id", "item_section", "section_title", "chunk_index",
          "token_count", "content")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    """Repository-relative when it can be, absolute when it cannot.

    An earlier version called Path.relative_to(ROOT) unconditionally and died
    on `--out data/dump`, a relative path, after the dump was already written:
    the work survived and the command it prints did not.
    """
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> int:
    ap = argparse.ArgumentParser(description="Dump the warehouse corpus")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data" / "warehouse_dump")
    args = ap.parse_args()
    args.out = args.out.resolve()

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set. Run `. .\\load-env.ps1` first.")
        return 2

    import numpy as np
    import psycopg2

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    # One query, one order. Ordering by (doc_id, chunk_index) rather than by
    # chunk_id: the serial is what a reload reissues, and the pair is what the
    # gold labels name.
    cur.execute(f"""select {', '.join(FIELDS)}, embedding
                    from chunks order by doc_id, chunk_index""")
    rows = cur.fetchall()
    if not rows:
        print("The warehouse has no chunks. Nothing to dump.")
        return 1

    chunks, vectors, missing = [], [], []
    for row in rows:
        record = dict(zip(FIELDS, row[:len(FIELDS)]))
        record["chunk_index"] = int(record["chunk_index"])
        chunks.append(record)
        raw = row[len(FIELDS)]
        if raw is None:
            missing.append((record["doc_id"], record["chunk_index"]))
            vectors.append(None)
        else:
            # pgvector hands back either a string like '[0.1,0.2]' or a list,
            # depending on whether the client registered its type.
            vectors.append([float(x) for x in
                            (raw.strip("[]").split(",")
                             if isinstance(raw, str) else raw)])

    print(f"{len(chunks)} chunks read, ordered by (doc_id, chunk_index)")
    if missing:
        print(f"\n{len(missing)} chunk(s) have no vector. A dump with holes "
              f"cannot be loaded:")
        for doc, idx in missing[:8]:
            print(f"  {doc} {idx}")
        print("\nRows with no vector are not part of a corpus src/load.py "
              "wrote.\nFind out what put them there before dumping.")
        return 1

    width = {len(v) for v in vectors}
    if len(width) != 1:
        print(f"Vectors have differing dimensions: {sorted(width)}. Stopping.")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    chunks_path = args.out / "chunks.json"
    vectors_path = args.out / "embeddings.npy"
    manifest_path = args.out / "manifest.json"

    chunks_path.write_text(json.dumps(chunks, indent=1, ensure_ascii=False),
                           encoding="utf-8")
    np.save(vectors_path, np.asarray(vectors, dtype=np.float32))

    src_manifest = ROOT / "data" / "manifest.json"
    if src_manifest.is_file():
        shutil.copy2(src_manifest, manifest_path)
    else:
        print("data/manifest.json not found; the dump has no manifest and "
              "load.py needs one.")

    # The assertion the docstring promises: read both files back and confirm
    # row i of the vectors belongs to chunk i of the text.
    reread = json.loads(chunks_path.read_text(encoding="utf-8"))
    revecs = np.load(vectors_path)
    ok = (len(reread) == len(revecs) == len(chunks)
          and all(reread[i]["doc_id"] == chunks[i]["doc_id"]
                  and reread[i]["chunk_index"] == chunks[i]["chunk_index"]
                  for i in range(len(chunks))))
    if not ok:
        print("The dump does not read back in the order it was written. "
              "Not usable.")
        return 1

    norms = np.linalg.norm(revecs, axis=1)
    (args.out / "MANIFEST.md").write_text("\n".join([
        "# Warehouse dump",
        "",
        f"Written {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by "
        f"`src/dump_warehouse.py`.",
        "",
        "This is the corpus every published figure was measured over: the one",
        "in the warehouse before the reload, with the section boundaries that",
        "commit `4001782` was written to fix and that never reached it —",
        "finding 18. It is not the corpus `data/chunks.json` holds, and it is",
        "not what the documented pipeline produces.",
        "",
        "Not committed: `.gitignore` excludes `data/`, and 6 MB of vectors do",
        "not belong in a repository. It is a working copy, and a working copy",
        "is exactly what finding 14 says cannot be relied on. The claim worth",
        "having is that the old parser rebuilds this text from filings pinned",
        "by accession number, and that is testable against these files rather",
        "than instead of them.",
        "",
        "| | |",
        "|---|---|",
        f"| chunks | {len(reread)} |",
        f"| vectors | {revecs.shape[0]} x {revecs.shape[1]}, "
        f"{revecs.dtype} |",
        f"| documents | {len({c['doc_id'] for c in reread})} |",
        f"| vector norms | min {norms.min():.6f}, max {norms.max():.6f} |",
        f"| `chunks.json` | `{sha256(chunks_path)}` |",
        f"| `embeddings.npy` | `{sha256(vectors_path)}` |",
        "",
        "Load it back with:",
        "",
        "```",
        f"python src/load.py --truncate \\",
        f"    --chunks {rel(chunks_path)} \\",
        f"    --vectors {rel(vectors_path)} \\",
        f"    --manifest {rel(manifest_path)}",
        "```",
        "",
        "`--truncate` reissues every `chunk_id`, so the ids in the published",
        "result files will not come back. The gold labels name a document and",
        "an index, which do.",
        "",
    ]), encoding="utf-8")

    print(f"\nwrote {rel(args.out)}/")
    print(f"  chunks.json     {chunks_path.stat().st_size / 1e6:.1f} MB")
    print(f"  embeddings.npy  {vectors_path.stat().st_size / 1e6:.1f} MB  "
          f"{revecs.shape}")
    print(f"  norms           min {norms.min():.6f}  max {norms.max():.6f}")
    print("\nText and vectors read back in the same order. Reconcile it before "
          "trusting it:")
    print(f"  python src/load.py --dry-run \\")
    print(f"      --chunks {rel(chunks_path)} \\")
    print(f"      --vectors {rel(vectors_path)} \\")
    print(f"      --manifest {rel(manifest_path)}")
    conn.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
