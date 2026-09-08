#!/usr/bin/env python3
"""
No text file in this repository contains a carriage return git cannot explain.

    python tests/test_line_endings.py

WHY THIS EXISTS

A single stray CR, invisible in every editor, blocked a merge, then a branch
switch, then a `git checkout --` that should have discarded it -- three times,
because .gitattributes rewrites line endings on the way in and out and the
rewritten file no longer matched itself. It cost more than any of the fourteen
findings, and it was one byte.

THE INVARIANT

Every CR is immediately followed by LF. That accepts a file stored LF and
checked out CRLF, which is what `* text=auto` produces on Windows, and rejects
the two forms that break the filter:

  CR CR LF   a CRLF file converted twice, the defect this was written for
  CR alone   an old-Mac ending, or the remains of a bad edit

It does not require a file to be uniform, because git decides that per platform
and this check has to pass on both.

WHY HERE AND NOT IN THE MAKEFILE

.github/workflows/ci.yml runs `tests/test_*.py`, so this is a gate the moment it
lands. `make test` used to name four files by hand and had already drifted from
that glob -- it was missing tests/test_harness.py, so a green `make test` and a
green CI were checking different things. The Makefile now uses the same wildcard.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Marked `binary` in .gitattributes: git never rewrites their bytes, so a CR in
# one of them is content, not a line ending.
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pyc", ".ico", ".woff",
          ".woff2", ".zip", ".gz", ".parquet", ".npy", ".safetensors"}


def tracked_text_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                         capture_output=True)
    if out.returncode != 0:
        print("git ls-files failed; is this a checkout?")
        raise SystemExit(2)
    files = []
    for name in out.stdout.decode("utf-8").split("\0"):
        if not name:
            continue
        path = ROOT / name
        if path.suffix.lower() in BINARY or not path.is_file():
            continue
        files.append(path)
    return files


def offences(data: bytes) -> list[tuple[int, str]]:
    """Line number and kind for every CR that is not part of a CRLF pair."""
    bad = []
    line = 1
    for i, byte in enumerate(data):
        if byte == 0x0A:
            line += 1
        elif byte == 0x0D:
            nxt = data[i + 1] if i + 1 < len(data) else None
            if nxt == 0x0D:
                bad.append((line, "CR CR  (a CRLF file converted twice)"))
            elif nxt != 0x0A:
                bad.append((line, "lone CR (no LF after it)"))
    return bad


def main() -> int:
    files = tracked_text_files()
    failures = 0

    for path in files:
        data = path.read_bytes()
        if b"\x00" in data[:8192]:
            continue                      # binary without a known extension
        bad = offences(data)
        if bad:
            failures += 1
            rel = path.relative_to(ROOT).as_posix()
            print(f"FAIL  {rel}")
            for line, kind in bad[:5]:
                print(f"      line {line}: {kind}")
            if len(bad) > 5:
                print(f"      ... {len(bad) - 5} more")

    print(f"\n{len(files) - failures} of {len(files)} tracked text files have "
          f"only well-formed line endings.")
    if failures:
        print(
            "\nA stray CR survives editors and diffs and then blocks a merge.\n"
            "Strip it at the byte level rather than renormalising, which hides\n"
            "it in a commit instead of removing it:\n"
            "  python -c \"p='FILE';d=open(p,'rb').read();"
            "open(p,'wb').write(d.replace(b'\\r\\r\\n',b'\\r\\n'))\""
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
