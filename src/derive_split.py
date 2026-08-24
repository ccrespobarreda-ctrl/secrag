#!/usr/bin/env python3
"""
Derive a split-specific question file from the master benchmark.

    python src/derive_split.py holdout --dry-run
    python src/derive_split.py holdout
    python src/derive_split.py --verify

The master benchmark carries all 100 questions; vnext_splits.yaml says which
split each one belongs to. Everything measured per split reads a derived file,
so a split is never executed by accident: the holdout cannot be run during
tuning if it is not in the file the tuning harness was pointed at.

WHY A SCRIPT AND NOT A HAND-EDITED FILE

The two derived files already in the repository were produced this way and say
so in their headers. A hand-edited third one would be a fourth place where the
benchmark is defined, free to drift from the other three with nothing to catch
it. --verify exists for that reason: it regenerates the two existing derived
files and compares them against what is on disk, so the deriving rule is
checked against its own past output before it is trusted with a new split.

ORDER

Questions come out in the order they appear in the master file, which is what
the existing derived files do. Order does not affect any metric, but a stable
order makes a diff between two regenerations readable.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml

HEADERS = {
    "holdout": (
        "# DERIVED FILE - do not edit by hand.\n"
        "# holdout split only, generated from questions_vnext.yaml and\n"
        "# vnext_splits.yaml. Sealed until the final evaluation: run once,\n"
        "# report, and do not tune against it afterwards.\n"
    ),
    "development": (
        "# DERIVED FILE - do not edit by hand.\n"
        "# development split only, generated from questions_vnext.yaml and\n"
        "# vnext_splits.yaml. Used to compare the new questions against the\n"
        "# legacy set in isolation. Holdout is absent by construction.\n"
    ),
    "regression+development": (
        "# DERIVED FILE - do not edit by hand.\n"
        "# regression + development only, generated from questions_vnext.yaml\n"
        "# and vnext_splits.yaml. The 30 holdout questions are deliberately\n"
        "# absent so they are never executed during tuning.\n"
    ),
}


def load(master: Path, splits: Path):
    questions = yaml.safe_load(master.read_text(encoding="utf-8"))
    spec = yaml.safe_load(splits.read_text(encoding="utf-8"))
    spec = {k: v for k, v in spec.items() if isinstance(v, list)}
    return questions, spec


def check_splits(questions, spec) -> list[str]:
    """
    The split file is a claim about the benchmark. Check it before using it.

    A question in two splits, or in none, silently changes what every per-split
    figure is measured over -- and nothing downstream would raise.
    """
    problems = []
    known = {q["id"] for q in questions}

    seen = Counter(qid for ids in spec.values() for qid in ids)
    for qid, n in sorted(seen.items()):
        if n > 1:
            where = sorted(k for k, v in spec.items() if qid in v)
            problems.append(f"{qid} appears in {n} splits: {where}")

    for qid in sorted(set(seen) - known):
        problems.append(f"{qid} is in a split but not in the master file")
    for qid in sorted(known - set(seen)):
        problems.append(f"{qid} is in the master file but in no split")

    return problems


def select(questions, spec, split: str):
    names = [s.strip() for s in split.split("+")]
    for name in names:
        if name not in spec:
            raise SystemExit(
                f"Unknown split {name!r}. Available: {', '.join(sorted(spec))}")
    wanted = {qid for name in names for qid in spec[name]}
    return [q for q in questions if q["id"] in wanted]


def summarise(rows, split: str) -> str:
    answerable = [q for q in rows if q.get("answerable")]
    labels = sum(len(q.get("gold_chunks") or q.get("gold_chunk_ids") or [])
                 for q in answerable)
    types = Counter(q["type"] for q in rows)

    out = [f"split          {split}",
           f"questions      {len(rows)}",
           f"  answerable   {len(answerable)}",
           f"  unanswerable {len(rows) - len(answerable)}",
           f"gold labels    {labels}",
           "by type"]
    for t, n in sorted(types.items()):
        out.append(f"  {t:<26}{n:>3}")
    return "\n".join(out)


def dump(rows, header: str) -> str:
    body = yaml.safe_dump(rows, sort_keys=False, allow_unicode=True,
                          default_flow_style=False, width=150)
    return header + body


def verify(questions, spec, base: Path) -> int:
    """Regenerate the derived files that already exist and compare."""
    cases = [("development", base / "questions_vnext_dev.yaml"),
             ("regression+development", base / "questions_vnext_tuning.yaml")]

    failures = 0
    for split, path in cases:
        if not path.exists():
            print(f"  {path.name:<34} skipped, not on disk")
            continue
        existing = yaml.safe_load(path.read_text(encoding="utf-8"))
        rebuilt = select(questions, spec, split)
        if existing == rebuilt:
            print(f"  {path.name:<34} matches ({len(rebuilt)} questions)")
        else:
            failures += 1
            old = [q["id"] for q in existing]
            new = [q["id"] for q in rebuilt]
            print(f"  {path.name:<34} DIFFERS")
            if old != new:
                print(f"    only on disk:  {sorted(set(old) - set(new))}")
                print(f"    only rebuilt:  {sorted(set(new) - set(old))}")
                if set(old) == set(new):
                    print("    same questions, different order")
            else:
                changed = [a["id"] for a, b in zip(existing, rebuilt) if a != b]
                print(f"    same ids, content differs: {changed}")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Derive a split-specific question file")
    ap.add_argument("split", nargs="?",
                    help="holdout, development, regression, "
                         "or a sum like regression+development")
    ap.add_argument("--master", type=Path, default=Path("eval/questions_vnext.yaml"))
    ap.add_argument("--splits", type=Path, default=Path("eval/vnext_splits.yaml"))
    ap.add_argument("--out", type=Path, help="defaults to eval/questions_vnext_<split>.yaml")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be written, write nothing")
    ap.add_argument("--verify", action="store_true",
                    help="regenerate the existing derived files and compare")
    args = ap.parse_args()

    for p in (args.master, args.splits):
        if not p.exists():
            print(f"{p} not found. Run this from the repository root.")
            return 2

    questions, spec = load(args.master, args.splits)

    problems = check_splits(questions, spec)
    if problems:
        print(f"{args.splits} does not describe {args.master} cleanly:\n")
        for p in problems:
            print(f"  {p}")
        print("\nNothing written. Fix the split file first: every per-split "
              "figure depends on it.")
        return 1

    print(f"{len(questions)} questions, {len(spec)} splits, all accounted for "
          f"exactly once\n")

    if args.verify:
        print("regenerating the derived files already on disk")
        failures = verify(questions, spec, args.master.parent)
        return 1 if failures else 0

    if not args.split:
        ap.error("a split is required unless --verify is given")

    rows = select(questions, spec, args.split)
    if not rows:
        print(f"No questions in split {args.split!r}.")
        return 1

    print(summarise(rows, args.split))

    out = args.out or (args.master.parent /
                       f"questions_vnext_{args.split.replace('+', '_')}.yaml")
    header = HEADERS.get(args.split, "# DERIVED FILE - do not edit by hand.\n"
                                     f"# {args.split} split only, generated from "
                                     f"{args.master.name} and {args.splits.name}.\n")
    text = dump(rows, header)

    if args.dry_run:
        print(f"\nwould write {out} ({len(text) / 1024:.0f} KB) -- nothing written")
        return 0

    if out.exists():
        print(f"\n{out} already exists. Delete it first, or pass --out.")
        return 1

    out.write_text(text, encoding="utf-8")
    print(f"\nwrote {out} ({len(text) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
