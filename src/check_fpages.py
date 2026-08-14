#!/usr/bin/env python3
"""
Confirm the recovered Item 8 sections actually contain financial statements.

    python src/check_fpages.py

The recovery captures from an anchor to the end of the document, so the
statements should be inside. "Should be" is the assumption worth testing: the
capture starts at whichever anchor appears first, and in at least one filing that
is the internal-control audit report rather than the statements themselves.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

# Every 10-K with audited statements contains these. If a recovered section is
# missing one, the capture started too late or ended too early.
REQUIRED = [
    "balance sheet",
    "statements of cash flows",
    "notes to",
]
# One of these must appear. Filers name the same statement several ways, and
# "comprehensive" sits between the words in a common variant, so a substring
# search for "statements of income" misses "statements of comprehensive income".
INCOME_ALIASES = [
    "statements of operations", "statement of operations",
    "statements of income", "statement of income",
    "statements of comprehensive income", "statement of comprehensive income",
    "statements of earnings", "statement of earnings",
]

# Printed when nothing matches, so the gap is diagnosed rather than guessed at.
import re
_HEADING_SCAN = re.compile(r"consolidated statements? of [a-z' ]{3,45}", re.I)


def main() -> int:
    parsed = Path(C.PARSED_DIR)
    files = sorted(parsed.glob("*.json"))
    if not files:
        print(f"No parsed JSON in {parsed}")
        return 2

    recovered, failures = [], []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("item8_recovered_from_fpages"):
            continue
        item8 = next((s for s in data["sections"] if s["item_section"] == "Item 8"), None)
        if not item8:
            continue

        text = item8["content"].lower()
        missing = [m for m in REQUIRED if m not in text]
        if not any(a in text for a in INCOME_ALIASES):
            missing.append("statements of operations/income")

        recovered.append((path.stem, item8["char_count"], missing))
        if missing:
            failures.append((path.stem, sorted(set(
                h.strip().lower() for h in _HEADING_SCAN.findall(item8["content"])))))

    if not recovered:
        print("No filings needed F-page recovery.")
        return 0

    print(f"{'filing':<24}{'chars':>10}   statements found")
    print("-" * 62)
    for name, n, missing in recovered:
        status = "all present" if not missing else "MISSING: " + ", ".join(missing)
        print(f"{name:<24}{n:>10,}   {status}")

    print()
    if failures:
        print(f"{len(failures)} recovered section(s) look incomplete.")
        print("Statement headings actually present, so the alias list can be fixed")
        print("rather than the capture:\n")
        for name, headings in failures:
            print(f"  {name}")
            for h in headings[:12]:
                print(f"      {h}")
            if not headings:
                print("      (none found — the capture, not the alias list, is wrong)")
        return 1

    print(f"{len(recovered)} recovered sections all contain the four core statements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
