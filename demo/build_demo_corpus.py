#!/usr/bin/env python3
"""
Build the demo corpus: the label fixture, plus its vectors.

    python demo/build_demo_corpus.py

Run once, by a maintainer, and commit the result. Whoever clones the repository
runs demo/load_demo.py instead and never needs this.

WHY NOT JUST ADD VECTORS TO tests/fixture_corpus.json

The two files hold the same 295 chunks and exist for opposite reasons.

tests/fixture_corpus.json exists so a check can fail. Its own docstring argues
that vectors would add half a megabyte of numbers verifying nothing, because
retrieval is not what the label check tests. That argument is still right, and
adding an embedding column to it would turn one file into two things.

This file exists so a stranger can watch the system work. It needs vectors and
does not need to be minimal.

Keeping them apart costs a megabyte and keeps each one arguable on its own
terms. Both are generated from the same source, so they cannot disagree about
what the corpus says.

THE VECTORS ARE COMPUTED THE WAY THE REAL ONES WERE

Same model, same normalization, passages raw with no query prefix -- the prefix
belongs on the query side only, and applying it here would put both sides in the
same skewed space and quietly degrade retrieval. src/embed.py explains this at
length; this script imports its verification rather than restating its rules, so
the demo cannot drift from the corpus it stands in for.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import config as C  # noqa: E402

log = logging.getLogger("demo-corpus")

FIXTURE = ROOT / "tests" / "fixture_corpus.json"
OUT = ROOT / "demo" / "demo_corpus.json"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Embed the label fixture into a self-contained demo corpus")
    ap.add_argument("--fixture", type=Path, default=FIXTURE)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--batch", type=int, default=C.EMBEDDING_BATCH_SIZE)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if not args.fixture.exists():
        log.error("%s not found. Build it first: python tests/fixture.py "
                  "--build", args.fixture)
        return 2

    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    chunks = data["chunks"]
    texts = [c["content"] for c in chunks]
    log.info("%d documents, %d chunks", len(data["documents"]), len(chunks))

    import numpy as np
    from sentence_transformers import SentenceTransformer
    from embed import verify

    log.info("Loading %s on CPU (downloads on first use)", C.EMBEDDING_MODEL)
    model = SentenceTransformer(C.EMBEDDING_MODEL, device="cpu")

    started = time.time()
    vectors = model.encode(
        texts,
        batch_size=args.batch,
        show_progress_bar=True,
        convert_to_numpy=True,
        # Passages raw. C.QUERY_PREFIX is applied by the retrieval path, never
        # here -- the same rule src/embed.py follows.
        normalize_embeddings=True,
    )
    log.info("%d vectors of %d dimensions in %.0fs",
             len(vectors), vectors.shape[1], time.time() - started)

    # The same checks the real embedding run is held to, imported rather than
    # rewritten. A demo whose vectors were verified more loosely than the
    # corpus's would be a demo of something else.
    problems = verify(vectors, chunks, model.tokenizer)
    if problems:
        log.error("Embedding verification failed; nothing written:")
        for p in problems:
            log.error("  %s", p)
        return 1

    payload = {
        "note": ("Self-contained demo corpus: the 295 chunks of "
                 "tests/fixture_corpus.json with their vectors. Every chunk a "
                 "gold label points at, plus its neighbours. Not the corpus, "
                 "which src/edgar.py fetches; see demo/README.md."),
        "source": args.fixture.name,
        "embedding_model": C.EMBEDDING_MODEL,
        "embedding_dim": int(vectors.shape[1]),
        "documents": data["documents"],
        "chunks": [
            dict(c, embedding=[round(float(x), 6) for x in v])
            for c, v in zip(chunks, vectors)
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False),
                        encoding="utf-8")
    size = args.out.stat().st_size / (1024 * 1024)
    log.info("wrote %s (%.1f MB)", args.out, size)
    log.info("Commit it. demo/load_demo.py reads this and needs nothing else.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
