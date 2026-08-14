#!/usr/bin/env python3
"""
Check that parsed sections are plausible.

    python src/verify_parse.py

Finding all six sections in all eighteen filings is not evidence that the
boundaries are right. A regex can match the correct heading and then run to the
wrong endpoint, producing a "section" that is half a page or three chapters. The
count would still be six.

These checks look for that. None of them proves correctness — only a human
reading a sample can do that — but each one catches a specific way boundary
detection goes wrong silently.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

# A 10-K section shorter than this is almost certainly a truncated capture or a
# contents line that survived. Item 3 (Legal Proceedings) is the legitimate
# exception and is excluded from the check.
MIN_PLAUSIBLE_CHARS = 1_500
SHORT_SECTION_EXEMPT = {"Item 3", "Item 7A"}

# Sections are subsets of the filing. If they sum to more than the whole, ranges
# overlap and the same text is indexed twice.
MAX_COVERAGE = 1.0


def check(parsed_dir: Path) -> int:
    files = sorted(parsed_dir.glob("*.json"))
    if not files:
        print(f"No parsed JSON in {parsed_dir} — run src/parse.py first")
        return 2

    problems: list[str] = []
    by_section: dict[str, list[int]] = {}
    rows = []

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        name = path.stem
        sections = {s["item_section"]: s["char_count"] for s in data["sections"]}
        total = data["total_chars"]
        covered = sum(sections.values())

        for item, n in sections.items():
            by_section.setdefault(item, []).append(n)

        rows.append((name, total, covered, sections))

        # 1. Sections cannot sum to more than the document.
        if covered > total * MAX_COVERAGE:
            problems.append(
                f"{name}: sections sum to {covered:,} of {total:,} chars — ranges overlap")

        # 2. Implausibly short sections.
        for item, n in sections.items():
            if item not in SHORT_SECTION_EXEMPT and n < MIN_PLAUSIBLE_CHARS:
                problems.append(f"{name}: {item} is only {n:,} chars")

        # 3. Risk Factors is normally the longest narrative section of a 10-K.
        #    If it is not, the boundary probably ended early.
        narrative = {k: v for k, v in sections.items() if k in ("Item 1", "Item 1A", "Item 7")}
        if narrative and max(narrative, key=narrative.get) != "Item 1A":
            longest = max(narrative, key=narrative.get)
            problems.append(
                f"{name}: {longest} ({narrative[longest]:,}) exceeds "
                f"Item 1A ({narrative.get('Item 1A', 0):,}) — check the boundary")

    # ── Per-filing table ──
    print(f"{'filing':<22}{'total':>9}{'covered':>9}{'%':>6}   ", end="")
    items = sorted(by_section, key=lambda i: (len(i), i))
    for item in items:
        print(f"{item:>9}", end="")
    print()
    print("-" * (46 + 9 * len(items)))

    for name, total, covered, sections in rows:
        pct = covered / total * 100 if total else 0
        print(f"{name:<22}{total:>9,}{covered:>9,}{pct:>5.0f}%   ", end="")
        for item in items:
            print(f"{sections.get(item, 0):>9,}", end="")
        print()

    # ── Distribution per section ──
    print(f"\n{'section':<10}{'n':>4}{'median':>10}{'min':>10}{'max':>10}"
          f"{'spread':>9}")
    print("-" * 53)
    for item in items:
        vals = by_section[item]
        med = statistics.median(vals)
        lo, hi = min(vals), max(vals)
        # A 20x spread across filings for the same section suggests the boundary
        # behaves differently on some documents.
        spread = hi / lo if lo else float("inf")
        flag = "  <-- wide" if spread > 20 else ""
        print(f"{item:<10}{len(vals):>4}{med:>10,.0f}{lo:>10,}{hi:>10,}"
              f"{spread:>8.1f}x{flag}")

    print()
    if problems:
        print(f"{len(problems)} checks failed:\n")
        for p in problems:
            print(f"  {p}")
        print("\nOpen one flagged filing in data/parsed and read the section by hand.")
        return 1

    print("All checks passed. This means the boundaries are plausible, not that they")
    print("are correct — read one filing's Item 1A end-to-end before trusting the corpus.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Sanity-check parsed sections")
    ap.add_argument("--parsed", default=C.PARSED_DIR, type=Path)
    return check(ap.parse_args().parsed)


if __name__ == "__main__":
    raise SystemExit(main())
