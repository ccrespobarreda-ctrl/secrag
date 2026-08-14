"""
Chunking tests.

Two bugs found here before the real corpus was ever touched, both the same
mistake in different clothes: estimating a token count instead of measuring it.

  1. Splitting an oversized paragraph by a proportional word step assumed tokens
     are linear in words. Measured 444 tokens against a 420 budget.

  2. Accumulating per-piece counts assumed token counts are additive across
     concatenation. They are not: a tokenizer segments the joined string, and
     per-piece rounding accumulates. Same overshoot, different cause.

A chunk over the model's limit is truncated in silence. Nothing downstream
reports it — vectors have the right dimension, search returns results, only
recall is quietly worse.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import chunk as CH
import config as C


def count(text: str) -> int:
    """Approximates WordPiece closely enough to exercise the boundary logic."""
    return max(1, int(len(text.split()) * 1.3))


BUDGET = C.CHUNK_TOKENS
OVERLAP = C.CHUNK_OVERLAP_TOKENS


def test_no_chunk_exceeds_budget_on_paragraphs():
    text = "\n\n".join(
        f"Paragraph {i}. " + "We rely on third-party manufacturers worldwide. " * 8
        for i in range(8))
    for c in CH.chunk_section(text, count, BUDGET, OVERLAP):
        assert count(c) <= BUDGET


def test_no_chunk_exceeds_budget_on_one_giant_paragraph():
    """Regression: proportional word stepping produced 444 against a 420 budget."""
    text = "This sentence describes an accounting policy in detail. " * 200
    chunks = CH.chunk_section(text, count, BUDGET, OVERLAP)
    assert len(chunks) > 1
    for c in chunks:
        assert count(c) <= BUDGET


def test_no_chunk_exceeds_budget_on_one_giant_sentence():
    """A flattened table arrives as one sentence with no punctuation to split on."""
    text = "word " * 900
    for c in CH.chunk_section(text, count, BUDGET, OVERLAP):
        assert count(c) <= BUDGET


def test_overlap_actually_happens():
    """Regression: with 60 tokens of overlap, no whole paragraph ever fit, so the
    carry-back silently never ran."""
    # Long enough to force several chunks: an earlier version of this test used
    # text under the budget, produced one chunk, and failed for the wrong reason.
    text = "\n\n".join(
        f"Risk factor {i}. "
        + "Disruption at a manufacturing partner could affect our delivery schedules materially. " * 10
        for i in range(8))
    chunks = CH.chunk_section(text, count, BUDGET, OVERLAP)
    assert len(chunks) > 2, f"expected several chunks, got {len(chunks)}"
    for a, b in zip(chunks, chunks[1:]):
        assert a.split("\n\n")[-1] in b


def test_tiny_chunks_dropped():
    assert CH.chunk_section("Short.", count, BUDGET, OVERLAP) == []


def test_budget_guard_accepts_a_fitting_model():
    class Model:
        max_seq_length = 512
    CH.verify_chunk_budget(Model())


def test_budget_guard_rejects_a_smaller_model():
    class Model:
        max_seq_length = 256
    try:
        CH.verify_chunk_budget(Model())
    except SystemExit:
        return
    raise AssertionError("a 256-token model must stop the run, not truncate silently")




def test_overlap_cannot_push_a_chunk_over_budget():
    """
    Regression from the real corpus: 115 of 4,176 chunks exceeded 420 tokens,
    peaking at 605.

    After emitting a chunk the carried overlap became the new chunk's opening,
    and the next paragraph was appended without re-checking. Carry of up to
    budget//2 plus a paragraph of nearly budget size starts the chunk already
    over the limit.
    """
    # Paragraphs sized so carry-back plus the next one would overflow.
    big = "Detailed accounting policy sentence about revenue recognition here. " * 40
    text = "\n\n".join(f"Section {i}. {big}" for i in range(6))
    chunks = CH.chunk_section(text, count, BUDGET, OVERLAP)
    assert len(chunks) > 2
    over = [c for c in chunks if count(c) > BUDGET]
    assert not over, f"{len(over)} chunks over budget, max {max(count(c) for c in over)}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}  {e}")
    print(f"\n{len(fns)} tests")
