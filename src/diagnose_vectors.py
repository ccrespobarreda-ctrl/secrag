#!/usr/bin/env python3
"""
Diagnose identical vectors produced from different text.

    python src/diagnose_vectors.py

Reads the saved vectors, so it costs nothing to run and needs no re-encoding.

The question it answers: when two different strings embed to the same vector, is
that a defect or is it the encoder behaving correctly?

The encoder does not see characters. It sees a token sequence. Two strings that
differ only in something the tokenizer discards -- trailing whitespace, a
character that maps to [UNK], a Unicode variant that normalizes away -- produce
the same tokens and therefore must produce the same vector.

If the token sequences match, the vectors are correct and the check comparing
against distinct *texts* is too strict. If they differ, the encoder received the
wrong input and that is a real bug.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("diagnose")


def main() -> int:
    ap = argparse.ArgumentParser(description="Explain duplicate vectors")
    ap.add_argument("--chunks", default="data/chunks.json", type=Path)
    ap.add_argument("--vectors", default="data/embeddings.npy", type=Path)
    ap.add_argument("--show", type=int, default=6, help="collisions to print")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    for p in (args.chunks, args.vectors):
        if not p.exists():
            print(f"{p} not found")
            return 2

    import numpy as np
    for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    from sentence_transformers import SentenceTransformer

    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    vectors = np.load(args.vectors)
    texts = [c["content"] for c in chunks]

    print(f"chunks            {len(chunks):>8,}")
    print(f"distinct texts    {len(set(texts)):>8,}")
    print(f"distinct vectors  {len({v.tobytes() for v in vectors}):>8,}")

    # Group chunk indices by vector.
    groups: dict[bytes, list[int]] = defaultdict(list)
    for i, v in enumerate(vectors):
        groups[v.tobytes()].append(i)

    collisions = [
        idxs for idxs in groups.values()
        if len(idxs) > 1 and len({texts[i] for i in idxs}) > 1
    ]

    if not collisions:
        print("\nEvery repeated vector comes from repeated text. Nothing to explain.")
        return 0

    print(f"\n{len(collisions)} vector(s) shared by differing text.\n")

    model = SentenceTransformer(C.EMBEDDING_MODEL, device="cpu")
    tokenizer = model.tokenizer

    same_tokens = 0
    for n, idxs in enumerate(collisions[:args.show], 1):
        unique = sorted({texts[i] for i in idxs})
        token_ids = [tuple(tokenizer.encode(t, add_special_tokens=True)) for t in unique]
        identical = len(set(token_ids)) == 1
        same_tokens += identical

        print(f"--- collision {n} ---")
        print(f"    chunks: {idxs}")
        print(f"    token sequences identical: {identical}")
        for t, ids in zip(unique, token_ids):
            print(f"      {len(t):>5} chars, {len(ids):>4} tokens  {t[:64]!r}")

        if identical and len(unique) == 2:
            a, b = unique
            # Show exactly which characters differ, since by definition the
            # tokenizer ignored them.
            extra = set(a) ^ set(b)
            print(f"      differ only in characters the tokenizer discards: "
                  f"{sorted(extra)!r}" if extra
                  else "      differ only in whitespace or ordering")
        print()

    print(f"{same_tokens} of {min(len(collisions), args.show)} shown collisions "
          f"have identical token sequences.")
    if same_tokens == min(len(collisions), args.show):
        print("The encoder is correct: identical tokens must give identical vectors.")
        print("The check should compare distinct vectors against distinct TOKEN")
        print("sequences, not distinct strings.")
    else:
        print("At least one collision has differing tokens. That is a real defect:")
        print("the encoder received the same input for different chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
