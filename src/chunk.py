#!/usr/bin/env python3
"""
Section-aware chunking.

    python src/chunk.py

CHUNK SIZE IS DICTATED BY THE MODEL, NOT BY PREFERENCE

The specification said 800 tokens. bge-small-en-v1.5 reports
max_seq_length = 512, and BERT-family encoders truncate past that in silence:
no error, no warning, the tail of every chunk simply does not reach the vector.
Retrieval degrades and nothing indicates why.

So the budget is 512 minus the [CLS] and [SEP] the tokenizer adds, minus headroom
for the metadata prefix. 420 content tokens with 60 of overlap leaves margin and
still holds a full risk factor, which runs 100-300 words in most filings.

verify_chunk_budget() below re-derives this at runtime from the loaded model. If
a future model reports a different limit, the run stops instead of quietly
truncating.

COUNT WITH THE MODEL'S OWN TOKENIZER

tiktoken is OpenAI's and segments differently from a BERT WordPiece vocabulary.
Counting 420 with one tokenizer and embedding with another means the 420 is
fiction. The model's tokenizer is used for both.

SPLIT ON PARAGRAPHS, NOT ON TOKEN COUNTS

A chunk cut mid-sentence embeds a fragment whose meaning is incomplete. Text is
accumulated paragraph by paragraph until the next one would exceed the budget.
Only a single paragraph longer than the whole budget is split further, and then
on sentence boundaries.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("chunk")

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass
class Chunk:
    doc_id: str
    item_section: str
    section_title: str
    chunk_index: int
    token_count: int
    content: str


def verify_chunk_budget(model) -> None:
    """
    Stop the run if the configured chunk size would be truncated.

    The failure this prevents is invisible at every other layer: embeddings are
    produced, vectors have the right dimension, search returns results. Only
    recall is quietly worse.
    """
    limit = getattr(model, "max_seq_length", None)
    if limit is None:
        log.warning("Model does not report max_seq_length; cannot verify the budget")
        return

    needed = C.CHUNK_TOKENS + 2          # [CLS] and [SEP]
    if needed > limit:
        raise SystemExit(
            f"CHUNK_TOKENS={C.CHUNK_TOKENS} plus 2 special tokens exceeds the "
            f"model limit of {limit}. Every chunk would be silently truncated at "
            f"{limit} tokens. Lower CHUNK_TOKENS in config.py to at most "
            f"{limit - 2}."
        )
    log.info("Chunk budget %d + 2 special tokens fits the model limit of %d",
             C.CHUNK_TOKENS, limit)


def split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in _PARAGRAPH.split(text)]
    return [p for p in parts if p]


def split_oversized(paragraph: str, count, budget: int) -> list[str]:
    """A paragraph longer than the whole budget, cut on sentence boundaries."""
    sentences = _SENTENCE.split(paragraph)
    out, current = [], []

    for sentence in sentences:
        n = count(sentence)
        if n > budget:
            # A single sentence over budget: tables and lists flattened into one
            # line do this. Cut on whitespace as a last resort.
            if current:
                out.append(" ".join(current))
                current = []
            # Words are not linear in tokens, so a proportional step overshoots:
            # measured at 444 tokens against a 420 budget. Accumulate and check
            # the real count instead of predicting it.
            words, buf = sentence.split(), []
            for word in words:
                buf.append(word)
                if count(" ".join(buf)) > budget:
                    buf.pop()
                    if buf:
                        out.append(" ".join(buf))
                    buf = [word]
            if buf:
                out.append(" ".join(buf))
            continue

        # Measure the joined text, not the sum of the parts. Token counts are
        # not additive across concatenation: a tokenizer segments the joined
        # string, and per-piece rounding accumulates. Summing produced chunks of
        # 444 tokens against a 420 budget while the accumulator believed it was
        # still under.
        if current and count(" ".join(current + [sentence])) > budget:
            out.append(" ".join(current))
            current = []
        current.append(sentence)

    if current:
        out.append(" ".join(current))
    return out


def chunk_section(text: str, count, budget: int, overlap: int) -> list[str]:
    paragraphs = []
    for p in split_paragraphs(text):
        paragraphs.extend([p] if count(p) <= budget
                          else split_oversized(p, count, budget))

    chunks: list[str] = []
    current: list[str] = []

    for para in paragraphs:
        # Same reasoning as split_oversized: the joined text is what gets
        # embedded, so the joined text is what gets measured.
        if current and count("\n\n".join(current + [para])) > budget:
            chunks.append("\n\n".join(current))

            # Overlap: carry back whole trailing paragraphs. Carrying tokens
            # rather than paragraphs would cut mid-sentence, which is what the
            # paragraph rule exists to prevent.
            #
            # The last paragraph is always carried, even when it alone exceeds
            # the overlap budget. Measured: with 60 tokens of overlap and filing
            # paragraphs of 130-170, no whole paragraph ever fit and the overlap
            # silently never happened. Its only cap is half the chunk budget, so
            # a long trailing paragraph cannot crowd out the next chunk.
            carried: list[str] = []
            for i, prev in enumerate(reversed(current)):
                candidate = [prev] + carried
                joined = count("\n\n".join(candidate))
                if i == 0:
                    if joined > budget // 2:
                        break
                elif joined > overlap:
                    break
                carried = candidate
                if joined >= overlap:
                    break

            # The carried overlap plus the incoming paragraph must still fit.
            # Without this check the new chunk starts already over budget:
            # measured 115 chunks above 420 with a maximum of 605, because
            # carry-back of up to budget//2 was added to a paragraph of nearly
            # budget size and never re-checked.
            #
            # Overlap is a convenience; the budget is not. Paragraphs are dropped
            # from the front of the carry until the pair fits.
            while carried and count("\n\n".join(carried + [para])) > budget:
                carried.pop(0)

            current = carried

        current.append(para)

    if current:
        chunks.append("\n\n".join(current))

    return [c for c in chunks if count(c) >= C.MIN_CHUNK_TOKENS]


def build_chunks(parsed_dir: Path, count) -> list[Chunk]:
    out: list[Chunk] = []

    for path in sorted(parsed_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        doc_id = path.stem
        index = 0

        for section in data["sections"]:
            pieces = chunk_section(section["content"], count,
                                   C.CHUNK_TOKENS, C.CHUNK_OVERLAP_TOKENS)
            for piece in pieces:
                out.append(Chunk(
                    doc_id=doc_id,
                    item_section=section["item_section"],
                    section_title=section["section_title"],
                    chunk_index=index,
                    token_count=count(piece),
                    content=piece,
                ))
                index += 1

        log.info("  %-24s %4d chunks", doc_id, index)

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Chunk parsed sections")
    ap.add_argument("--parsed", default=C.PARSED_DIR, type=Path)
    ap.add_argument("--out", default="data/chunks.json", type=Path)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from sentence_transformers import SentenceTransformer

    log.info("Loading %s to count tokens the way the encoder does", C.EMBEDDING_MODEL)
    model = SentenceTransformer(C.EMBEDDING_MODEL)
    verify_chunk_budget(model)

    tokenizer = model.tokenizer

    # The tokenizer warns whenever it encodes text past the model limit. Inside
    # the measuring loop that is expected: candidates are deliberately counted
    # before being rejected, so the warning fires thousands of times and buries
    # the output.
    #
    # It is silenced only around this call, not for the process. Anywhere else --
    # at embedding time above all -- text over the limit is a real defect and the
    # warning has to survive to say so.
    tok_log = logging.getLogger("transformers.tokenization_utils_base")

    def count(text: str) -> int:
        previous = tok_log.level
        tok_log.setLevel(logging.ERROR)
        try:
            return len(tokenizer.encode(text, add_special_tokens=False))
        finally:
            tok_log.setLevel(previous)

    chunks = build_chunks(args.parsed, count)
    if not chunks:
        log.error("No chunks produced — run src/parse.py first")
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps([asdict(c) for c in chunks], indent=1),
                        encoding="utf-8")

    counts = [c.token_count for c in chunks]
    over = [c for c in chunks if c.token_count > C.CHUNK_TOKENS]

    log.info("%s chunks from %d filings -> %s",
             f"{len(chunks):,}", len(list(args.parsed.glob('*.json'))), args.out)
    log.info("  tokens  min %d  median %d  max %d",
             min(counts), sorted(counts)[len(counts) // 2], max(counts))

    if over:
        log.error("%d chunks exceed CHUNK_TOKENS=%d and would be truncated",
                  len(over), C.CHUNK_TOKENS)
        return 1

    log.info("  no chunk exceeds the budget, so nothing will be truncated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
