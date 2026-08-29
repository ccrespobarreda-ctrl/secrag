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
it. --verify exists for that reason: it regenerates every derived file and compares
it against what is on disk, so the deriving rule is checked against its own past
output before it is trusted with a new split.

WHAT --verify CHECKS, AND WHY EACH PART IS THERE

It used to cover two of the four files and to print "skipped, not on disk" for a
file that was absent, then exit 0. A check that passes because there was nothing
to check is the failure this repository exists to document, and it was sitting
inside the tool that guards the benchmark. An absent derived file is now a
failure: the split it defines is measured somewhere, and a missing file means
that measurement is reading something else or nothing at all.

The header is compared too, and a file that will not parse is reported rather
than raised. One of these files was found with a shell command pasted onto its
first line, which left it unreadable as YAML. Nothing noticed, and the reason is
worth stating plainly: the damage was not subtle, it was that no check looked at
that file. Two of the four were covered and the holdout had not been executed
since. From the outside a corrupt file and an unchecked file look the same, which
is the whole argument for checking all of them.

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

# One place where a split's name, its file and its header live together. They
# used to be apart, and the file this script wrote (questions_vnext_development)
# was not the file --verify looked for (questions_vnext_dev), so every
# regeneration ended in a manual rename -- which is a step where a file gets
# renamed onto the wrong one.
DERIVED = {
    "regression": ("questions_vnext_regression.yaml",
        "# DERIVED FILE - do not edit by hand.\n"
        "# regression split only, generated from questions_vnext.yaml and\n"
        "# vnext_splits.yaml. The original 50 questions, written before the\n"
        "# system existed; the published retrieval figure is measured here.\n"
    ),
    "holdout": ("questions_vnext_holdout.yaml",
        "# DERIVED FILE - do not edit by hand.\n"
        "# holdout split only, generated from questions_vnext.yaml and\n"
        "# vnext_splits.yaml. Sealed until the final evaluation: run once,\n"
        "# report, and do not tune against it afterwards.\n"
    ),
    "development": ("questions_vnext_dev.yaml",
        "# DERIVED FILE - do not edit by hand.\n"
        "# development split only, generated from questions_vnext.yaml and\n"
        "# vnext_splits.yaml. Used to compare the new questions against the\n"
        "# legacy set in isolation. Holdout is absent by construction.\n"
    ),
    "regression+development": ("questions_vnext_tuning.yaml",
        "# DERIVED FILE - do not edit by hand.\n"
        "# regression + development only, generated from questions_vnext.yaml\n"
        "# and vnext_splits.yaml. The 30 holdout questions are deliberately\n"
        "# absent so they are never executed during tuning.\n"
    ),
}


def header_for(split: str, master: Path, splits: Path) -> str:
    if split in DERIVED:
        return DERIVED[split][1]
    return ("# DERIVED FILE - do not edit by hand.\n"
            f"# {split} split only, generated from {master.name} and "
            f"{splits.name}.\n")


def path_for(split: str, base: Path, master: Path) -> Path:
    if split in DERIVED:
        return base / DERIVED[split][0]
    return base / f"questions_vnext_{split.replace('+', '_')}.yaml"


def header_of(text: str) -> str:
    """The leading comment block of a derived file, as written."""
    out = []
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        out.append(line)
    return "\n".join(out) + ("\n" if out else "")


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


def verify(questions, spec, base: Path, master: Path, splits: Path) -> int:
    """Regenerate every derived file and compare it against what is on disk."""
    failures = 0
    for split in DERIVED:
        path = path_for(split, base, master)
        if not path.exists():
            failures += 1
            print(f"  {path.name:<34} MISSING")
            print(f"    the {split} split is measured somewhere; regenerate it:")
            print(f"      python src/derive_split.py {split} --force")
            continue

        text = path.read_text(encoding="utf-8")
        rebuilt = select(questions, spec, split)

        want_header = header_for(split, master, splits)
        got_header = header_of(text)
        if got_header != want_header:
            failures += 1
            print(f"  {path.name:<34} HEADER DIFFERS")
            for line in got_header.splitlines():
                if line not in want_header.splitlines():
                    print(f"    on disk, not generated:  {line!r}")
            for line in want_header.splitlines():
                if line not in got_header.splitlines():
                    print(f"    generated, not on disk:  {line!r}")
            print("    A derived file says it is not edited by hand, and this "
                  "is the only\n    check that reads its header. Regenerate "
                  "rather than repair.")
            continue

        # A file damaged above the questions may not parse at all. That is a
        # result, not a crash: reporting it here is the difference between the
        # tool naming the broken file and a traceback saying yaml did not like
        # something.
        try:
            existing = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            failures += 1
            print(f"  {path.name:<34} WILL NOT PARSE")
            print(f"    {str(exc).splitlines()[0]}")
            print(f"    Regenerate it: python src/derive_split.py {split} "
                  f"--force")
            continue

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
                    help="regenerate every derived file and compare")
    ap.add_argument("--force", action="store_true",
                    help="overwrite the derived file if it already exists")
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
        print(f"regenerating all {len(DERIVED)} derived files and comparing")
        failures = verify(questions, spec, args.master.parent, args.master,
                          args.splits)
        if failures:
            print(f"\n{failures} of {len(DERIVED)} derived file(s) do not match "
                  f"the master benchmark.\nEvery per-split figure is measured "
                  f"against these.")
        return 1 if failures else 0

    if not args.split:
        ap.error("a split is required unless --verify is given")

    rows = select(questions, spec, args.split)
    if not rows:
        print(f"No questions in split {args.split!r}.")
        return 1

    print(summarise(rows, args.split))

    out = args.out or path_for(args.split, args.master.parent, args.master)
    header = header_for(args.split, args.master, args.splits)
    text = dump(rows, header)

    if args.dry_run:
        print(f"\nwould write {out} ({len(text) / 1024:.0f} KB) -- nothing written")
        return 0

    if out.exists() and not args.force:
        print(f"\n{out} already exists. Pass --force to overwrite it, or --out "
              f"to write elsewhere.")
        return 1

    out.write_text(text, encoding="utf-8")
    print(f"\nwrote {out} ({len(text) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
