#!/usr/bin/env python3
"""
Tests for the evaluation harness itself.

    python tests/test_harness.py

WHY THESE PARTICULAR TESTS

Every case here corresponds to a defect that shipped and was found by reading
output rather than by anything failing. None of them would have been caught by
the unit tests that already existed, because none of them raised an error: they
returned plausible numbers and destroyed data quietly.

  - --no-cache saved an empty cache over a real one
  - LIKE read the % of a percentage as a wildcard
  - stored line breaks hid multi-word anchors from a literal search

A test for a bug that never raised is worth more than a test for one that did.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

PASSED = FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name}   {detail}")


# ── the cache guard ──────────────────────────────────────────────────
def test_no_cache_does_not_overwrite() -> None:
    """--no-cache must leave an existing cache untouched."""
    import evaluate_generation as EG

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cache.json"
        real = {"question-a": "an expensive answer",
                "question-b": "another expensive answer"}
        path.write_text(json.dumps(real), encoding="utf-8")

        original = EG.CACHE_PATH
        try:
            EG.CACHE_PATH = path

            EG.save_cache({}, enabled=False)
            after = json.loads(path.read_text(encoding="utf-8"))
            check("--no-cache leaves the cache on disk untouched",
                  after == real, f"cache became {after}")

            EG.save_cache({"question-c": "new"}, enabled=True)
            after = json.loads(path.read_text(encoding="utf-8"))
            check("caching on still writes",
                  after == {"question-c": "new"}, f"cache became {after}")
        finally:
            EG.CACHE_PATH = original


def test_save_cache_defaults_to_writing() -> None:
    """The guard must not silently disable caching for existing callers."""
    import evaluate_generation as EG

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cache.json"
        original = EG.CACHE_PATH
        try:
            EG.CACHE_PATH = path
            EG.save_cache({"k": "v"})
            check("save_cache writes when enabled is not given",
                  path.exists() and
                  json.loads(path.read_text(encoding="utf-8")) == {"k": "v"})
        finally:
            EG.CACHE_PATH = original


# ── anchor counting ──────────────────────────────────────────────────
def test_percent_is_not_a_wildcard() -> None:
    """An anchor holding a percentage must be matched literally."""
    import fix_anchors as FA

    chunks = ["Europe and Asia contributed 45% of net revenues",
              "the rate rose 45 basis points to 4512 units",
              "unrelated text with no figure at all"]
    FA._DOC_CACHE.clear()
    FA._DOC_CACHE["DOC"] = [FA._flat(c) for c in chunks]

    n = FA.count_in_document(None, "DOC", "45%")
    check("'45%' matches only the chunk containing it", n == 1,
          f"got {n}, expected 1")

    n = FA.count_in_document(None, "DOC", "45")
    check("'45' matches both chunks that contain it", n == 2,
          f"got {n}, expected 2")


def test_line_breaks_do_not_hide_an_anchor() -> None:
    """Text is compared flattened, because filings break tables across lines."""
    import fix_anchors as FA

    raw = "Old Navy Global 3 %\n3 %\nGap Global 6 %\n4 %"
    FA._DOC_CACHE.clear()
    FA._DOC_CACHE["DOC"] = [FA._flat(raw)]

    anchor = "Old Navy Global 3 % 3 % Gap Global 6 % 4 %"
    check("a multi-word anchor survives the line breaks of a table",
          FA.count_in_document(None, "DOC", anchor) == 1,
          "the raw text has newlines where the anchor has spaces")

    check("flattening is applied to the needle as well",
          FA.count_in_document(None, "DOC", "Old Navy Global 3 %\n3 %") == 1)


def test_anchor_absent_reports_zero() -> None:
    """Zero must be distinguishable from one; it means a broken anchor."""
    import fix_anchors as FA

    FA._DOC_CACHE.clear()
    FA._DOC_CACHE["DOC"] = ["some text that does not contain the phrase"]
    check("an anchor that is not there counts zero",
          FA.count_in_document(None, "DOC", "a phrase that is absent") == 0)


# ── anchor extension ─────────────────────────────────────────────────
def test_extension_keeps_the_original_anchor() -> None:
    """An extension is the anchor plus context, never a replacement."""
    import fix_anchors as FA

    chunks = ["Net revenues 4,966,370 5,701,942 Cost of goods sold",
              "Total net revenues were 4,966,370 thousand compared with",
              "segment table 4,966,370 North America 2,859,420"]
    FA._DOC_CACHE.clear()
    FA._DOC_CACHE["DOC"] = [FA._flat(c) for c in chunks]

    original_chunk_text = FA.chunk_text
    try:
        FA.chunk_text = lambda cur, doc, idx: chunks[idx]
        grown, n = FA.extend_anchor(None, "DOC", 0, "4,966,370")
        check("the extension still contains the original anchor",
              "4,966,370" in grown, f"got {grown!r}")
        check("the extension identifies one chunk", n == 1, f"got {n}")
        check("the extension is longer than the anchor",
              len(grown) > len("4,966,370"), f"got {grown!r}")

        grown2, _ = FA.extend_anchor(None, "DOC", 2, "4,966,370")
        check("a different chunk grows in a different direction",
              grown2 != grown, f"both gave {grown!r}")
    finally:
        FA.chunk_text = original_chunk_text


def test_extension_starts_from_several_occurrences() -> None:
    """The first occurrence of a common word is usually the least useful one."""
    import fix_anchors as FA

    chunk = ("2025 Table of Contents 2025 Form 10-K 2025 "
             "Net sales by channel 2025 Online 4,132")
    others = ["2025 Table of Contents 2025 Form 10-K 2025 other content here",
              "2025 Table of Contents 2025 Form 10-K 2025 third variant"]
    FA._DOC_CACHE.clear()
    FA._DOC_CACHE["DOC"] = [FA._flat(c) for c in [chunk] + others]

    original_chunk_text = FA.chunk_text
    try:
        FA.chunk_text = lambda cur, doc, idx: chunk
        grown, n = FA.extend_anchor(None, "DOC", 0, "2025")
        check("growing from a later occurrence finds the distinctive one",
              n == 1, f"got {n} matches with {grown!r}")
        check("the result still contains the anchor", "2025" in grown)
    finally:
        FA.chunk_text = original_chunk_text


def main() -> int:
    print("cache guard")
    test_no_cache_does_not_overwrite()
    test_save_cache_defaults_to_writing()
    print("\nanchor counting")
    test_percent_is_not_a_wildcard()
    test_line_breaks_do_not_hide_an_anchor()
    test_anchor_absent_reports_zero()
    print("\nanchor extension")
    test_extension_keeps_the_original_anchor()
    test_extension_starts_from_several_occurrences()

    print(f"\n{PASSED + FAILED} tests, {PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
