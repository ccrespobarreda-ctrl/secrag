#!/usr/bin/env python3
"""
Print one parsed section, to read a boundary by hand.

    python src/inspect_section.py CROX "Item 8"

Automated checks can say a section is implausible. Only reading it says why.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("filing", help="ticker or filename stem, e.g. CROX")
    ap.add_argument("section", nargs="?", default="Item 8")
    ap.add_argument("--chars", type=int, default=1200)
    ap.add_argument("--parsed", default=C.PARSED_DIR, type=Path)
    args = ap.parse_args()

    matches = list(args.parsed.glob(f"{args.filing}*.json"))
    if not matches:
        print(f"No parsed file matching {args.filing} in {args.parsed}")
        return 2

    data = json.loads(matches[0].read_text(encoding="utf-8"))
    for s in data["sections"]:
        if s["item_section"].lower() != args.section.lower():
            continue
        print(f"=== {matches[0].stem} / {s['item_section']} "
              f"({s['char_count']:,} chars) ===")
        print(f"heading as found: {s['heading_as_found']!r}\n")
        print(s["content"][:args.chars])
        if s["char_count"] > args.chars:
            print(f"\n... [{s['char_count'] - args.chars:,} more chars]")
        return 0

    found = [s["item_section"] for s in data["sections"]]
    print(f"{args.section} not in {matches[0].stem}. Sections present: {found}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
