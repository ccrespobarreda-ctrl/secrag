#!/usr/bin/env python3
"""
Verify the frozen release artifacts against SHA256SUMS.txt.

    python verify_release.py

WHY THIS IS NOT `sha256sum -c SHA256SUMS.txt`

The hashes were computed on Windows, over CRLF line endings. .gitattributes
stores text with LF and checks it out however the platform wants, so a clone on
Linux or macOS holds the same content in different bytes and a plain
`sha256sum -c` mismatches every entry. That is a property of the checkout, not
of the release, and it is why this list went unchecked for weeks while one of
its entries was false.

The hashed bytes are recoverable, so they are recovered here rather than the
hashes rewritten: FINAL_RELEASE_MANIFEST.md carries the same twelve hashes in
the same form and is itself frozen, so recomputing would leave two published
documents disagreeing about one artifact.

TWO CLAIMS, CHECKED AGAINST TWO DIFFERENT THINGS

The list makes two claims that cannot both be checked the same way. "This
evidence has not been edited" is true of the results files and the configuration
and is verified against the working tree. "This is the code that produced those
figures" is not a claim about the disk: the harness is meant to keep changing,
and findings 3, 7 and 11 in the README are each an edit to one of those modules.
Hashing a moving file against a fixed value produces a permanently red build,
and a permanently red build gets switched off. Those entries are verified
against the tag the release was cut from, read out of git rather than off the
disk. A `#@ verify` line in SHA256SUMS.txt selects which.

WHY PYTHON AND NOT A SHELL SCRIPT

The first version of this was shell, and `perl` and `sha256sum` do not exist on
Windows outside Git Bash, where `bash` resolves to the WSL launcher instead.
Python is already a hard dependency of this repository and of the workflow, so
this file is the one implementation that both a person and the gate can run. A
local check that is not the same code as the gate will disagree with it
eventually -- `make test` runs four test files and CI runs five, for exactly
that reason.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUMS = ROOT / "SHA256SUMS.txt"
ENTRY = re.compile(rb"^([0-9A-Fa-f]{64})[ *]+(.+?)\s*$")
DIRECTIVE = re.compile(rb"^#@\s*verify\s+(tree|ref|record)(?:\s+(\S+))?\s*$")


def crlf_digest(data: bytes) -> str:
    """SHA-256 over the bytes as hashed: text normalised to CRLF.

    Idempotent, so it gives the same answer on a CRLF working tree, an LF
    checkout and a blob read out of git. A lone CR is left alone, and a final
    line without a newline keeps not having one -- `sed 's/$/\\r/'` adds one and
    changes the digest.
    """
    data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return hashlib.sha256(data).hexdigest().upper()


def blob_at(ref: str, rel: str) -> bytes:
    """The file as it stood at a tag, read from git rather than from the disk.

    These paths are the harness and the retriever, and they are meant to keep
    changing; the release is the commit, not the current working tree.
    """
    out = subprocess.run(["git", "show", f"{ref}:{rel}"],
                         cwd=ROOT, capture_output=True)
    if out.returncode != 0:
        raise FileNotFoundError(out.stderr.decode(errors="replace").strip())
    return out.stdout


def main() -> int:
    if not SUMS.exists():
        print(f"{SUMS.name} not found next to this script.")
        return 2

    mode, ref = "tree", None
    checked = failed = 0
    for raw in SUMS.read_bytes().splitlines():
        d = DIRECTIVE.match(raw)
        if d:
            mode = d.group(1).decode()
            ref = d.group(2).decode() if d.group(2) else None
            if mode == "ref" and not ref:
                print("A `#@ verify ref` line names no ref.")
                return 2
            label = {"tree": "against the working tree",
                     "record": "recorded, not verifiable -- see SHA256SUMS.txt"}.get(
                         mode, f"against tag {ref}")
            print(f"\n-- {label}")
            continue

        m = ENTRY.match(raw)
        if not m:
            continue                      # comments, blank lines
        want = m.group(1).decode().upper()
        rel = m.group(2).decode("utf-8").lstrip("./")

        if mode == "record":
            # Hashed from a working tree that was never committed, so there is
            # nothing to compare against. Printed so the value stays visible and
            # counted nowhere, because a check that can never pass is not a
            # check -- it is a permanently red build waiting to be switched off.
            print(f"record   {rel}")
            continue

        checked += 1

        try:
            data = ((ROOT / rel).read_bytes() if mode == "tree"
                    else blob_at(ref, rel))
        except (FileNotFoundError, OSError) as exc:
            print(f"MISSING  {rel}")
            if mode == "ref":
                print(f"         {exc}")
                print(f"         the release tag {ref} is gone, or the path is")
                print(f"         not in it. Recreate it: the commit is the release.")
            failed += 1
            continue

        got = crlf_digest(data)
        if got == want:
            print(f"ok       {rel}")
        else:
            print(f"FAIL     {rel}")
            print(f"         recorded {want}")
            print(f"         found    {got}")
            failed += 1

    print(f"\n{checked - failed} of {checked} artifacts match what was published.")
    if failed:
        print(
            "\nAn artifact of the frozen release no longer matches the bytes it\n"
            "was published as. The fix is not to recompute the hash.\n"
            "SHA256SUMS.txt records what was measured, and the freeze rule in\n"
            "FINAL_RELEASE_MANIFEST.md says a change to configuration, benchmark\n"
            "labels, prompts, generation code or result files constitutes a new\n"
            "evaluation version and must not be reported as this release."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # `python verify_release.py | head` closes the pipe early. Without this
        # the script dies with a traceback and an exit code that means nothing.
        sys.stderr.close()
        raise SystemExit(1)
