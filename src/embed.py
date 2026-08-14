#!/usr/bin/env python3
"""
Compute embeddings locally, on CPU.

    python src/embed.py

Local for two reasons. It is free, and it keeps the corpus and its vectors on the
machine — only the generation call ever crosses the network. For a client whose
data cannot leave their network, that is the difference between a system they can
use and one they cannot.

TWO DETAILS THAT ARE EASY TO GET WRONG AND HARD TO DEBUG

Passages are embedded raw. bge models are trained with an instruction prefix on
the *query* side only:

    "Represent this sentence for searching relevant passages: {query}"

Applying it to passages as well puts both sides in the same skewed space, and
retrieval degrades without any error to point at. The prefix lives in
config.QUERY_PREFIX and is applied in the retrieval path, never here.

Vectors are normalized to unit length. pgvector's cosine operator handles
unnormalized input correctly, so this is not required for `<=>` — but it makes
inner product equivalent to cosine, which keeps the door open to the faster
operator later without silently changing what "similar" means.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("embed")


def verify(vectors, chunks, tokenizer=None) -> list[str]:
    """
    Checks that catch a silently broken embedding run.

    None of these fire on a healthy run, and each corresponds to a failure that
    produces plausible-looking output: right row count, right dimension, search
    returns results, only relevance is wrong.
    """
    import numpy as np

    problems = []

    if len(vectors) != len(chunks):
        problems.append(f"{len(vectors)} vectors for {len(chunks)} chunks")

    dim = vectors.shape[1]
    if dim != C.EMBEDDING_DIM:
        problems.append(
            f"model returned {dim} dimensions, config.EMBEDDING_DIM is "
            f"{C.EMBEDDING_DIM}, and the warehouse column is vector"
            f"({C.EMBEDDING_DIM})")

    if not np.isfinite(vectors).all():
        n = int((~np.isfinite(vectors)).any(axis=1).sum())
        problems.append(f"{n} vectors contain NaN or infinity")

    norms = np.linalg.norm(vectors, axis=1)
    if np.abs(norms - 1.0).max() > 1e-3:
        problems.append(
            f"vectors are not unit length (max deviation "
            f"{np.abs(norms - 1.0).max():.4f}) — normalize_embeddings was not applied")

    # Duplicate vectors are a defect only when the *input to the encoder* differs,
    # and the encoder's input is a token sequence, not a string.
    #
    # Two facts, both established by measurement rather than assumed:
    #
    #   1. SEC filings repeat boilerplate verbatim. The PCAOB auditor's report
    #      appears identically across companies; three chunks in this corpus are
    #      the same 2,422-character "Basis for Opinions" passage. Identical text
    #      must embed to an identical vector.
    #
    #   2. Strings that differ can still tokenize identically, when the difference
    #      lies in characters the tokenizer discards. Comparing against distinct
    #      strings therefore flags correct behaviour as a fault.
    #
    # Tokenizing 4,000 chunks is not free, so it runs only when the cheap check
    # fails and a real answer is needed.
    distinct_vectors = len({v.tobytes() for v in vectors})
    distinct_texts = len({c["content"] for c in chunks})

    if distinct_vectors < distinct_texts:
        if tokenizer is None:
            problems.append(
                f"{distinct_vectors} distinct vectors for {distinct_texts} "
                f"distinct texts, and no tokenizer was supplied to tell whether "
                f"that is legitimate")
        else:
            distinct_tokens = len({
                tuple(tokenizer.encode(c["content"], add_special_tokens=True))
                for c in chunks
            })
            if distinct_vectors < distinct_tokens:
                problems.append(
                    f"{distinct_vectors} distinct vectors for {distinct_tokens} "
                    f"distinct token sequences — the encoder received the same "
                    f"input more than once")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Embed chunks locally on CPU")
    ap.add_argument("--chunks", default="data/chunks.json", type=Path)
    ap.add_argument("--out", default="data/embeddings.npy", type=Path)
    ap.add_argument("--batch", type=int, default=C.EMBEDDING_BATCH_SIZE)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if not args.chunks.exists():
        log.error("%s not found — run src/chunk.py first", args.chunks)
        return 2

    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    texts = [c["content"] for c in chunks]
    log.info("%s chunks to embed", f"{len(texts):,}")

    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(C.EMBEDDING_MODEL, device="cpu")
    log.info("Loaded %s (max_seq_length=%d) on CPU",
             C.EMBEDDING_MODEL, model.max_seq_length)

    # Defense in depth. chunk.py already guarantees this, but that guarantee is
    # only as good as the chunks file matching the config that produced it.
    tokenizer = model.tokenizer
    over = [i for i, t in enumerate(texts)
            if len(tokenizer.encode(t, add_special_tokens=True)) > model.max_seq_length]
    if over:
        log.error("%d chunks exceed the model limit and would be truncated. "
                  "Re-run src/chunk.py — data/chunks.json was built with a "
                  "different budget.", len(over))
        return 1

    started = time.time()
    vectors = model.encode(
        texts,
        batch_size=args.batch,
        show_progress_bar=True,
        convert_to_numpy=True,
        # Passages raw: the instruction prefix belongs on the query side only.
        normalize_embeddings=True,
    )
    elapsed = time.time() - started

    # Saved before verification. Encoding 4,000 chunks on CPU takes a quarter of
    # an hour, and discarding that work because a check failed means paying for
    # it again to look at the same numbers. The non-zero exit still stops the
    # pipeline; the vectors are simply on disk while the failure is diagnosed.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.out, vectors.astype(np.float32))

    problems = verify(vectors, chunks, tokenizer)
    if problems:
        log.error("Embedding verification failed (vectors saved to %s anyway):",
                  args.out)
        for p in problems:
            log.error("  %s", p)
        return 1

    log.info("%s vectors of %d dimensions in %.0fs (%.0f chunks/s) -> %s",
             f"{len(vectors):,}", vectors.shape[1], elapsed,
             len(vectors) / max(elapsed, 1e-9), args.out)
    from collections import Counter
    repeated = [(t, n) for t, n in Counter(texts).items() if n > 1]
    if repeated:
        total = sum(n - 1 for _, n in repeated)
        log.info("  %d chunk texts appear more than once (%d redundant chunks). "
                 "Boilerplate repeated across filings; identical text embeds to "
                 "an identical vector by design.", len(repeated), total)
        for text, n in sorted(repeated, key=lambda x: -x[1])[:3]:
            log.info("      x%d  %s", n, text[:72].replace("\n", " "))

    # Repeated passages are not an error, but they do occupy retrieval slots
    # three times over for the same content. Worth knowing before evaluating
    # recall.
    distinct_tokens = len({
        tuple(tokenizer.encode(t, add_special_tokens=True)) for t in texts
    })
    if distinct_tokens < len(texts):
        log.info("  %d chunks are duplicates once tokenized (%d distinct "
                 "sequences). Boilerplate repeated across filings; they will "
                 "compete for the same retrieval slots.",
                 len(texts) - distinct_tokens, distinct_tokens)

    log.info("  all finite, unit length, and no input was encoded twice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
