#!/usr/bin/env python3
"""
Which commit, if any, holds the bytes SHA256SUMS.txt recorded?

    python find_release_commit.py

WHY

The release hashes were computed at 17:42 on 17 August, over a working tree.
The commit that says it finalises the release is dated the 18th, and its blobs
do not match: verify_release.py reports five mismatches against the tag, and
two of those files are byte-identical to the current working tree, so the
mismatch is not simply the harness having moved on.

Either the hashed bytes are in some commit -- in which case that commit is the
release and the tag belongs on it -- or they are in none, and the frozen release
describes a working tree that was never committed. That is a much larger claim
and it should be established rather than assumed, in either direction.

This walks every commit that touched each recorded path, hashes its blob the
same way verify_release.py does, and reports where each recorded hash is found.
It reads history and writes nothing.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUMS = ROOT / "SHA256SUMS.txt"
ENTRY = re.compile(rb"^([0-9A-Fa-f]{64})[ *]+(.+?)\s*$")
DIRECTIVE = re.compile(rb"^#@\s*verify\s+(tree|ref)(?:\s+(\S+))?\s*$")


def git(*args: str) -> bytes:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode(errors="replace").strip())
    return out.stdout


def crlf_digest(data: bytes) -> str:
    data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return hashlib.sha256(data).hexdigest().upper()


def main() -> int:
    recorded: list[tuple[str, str]] = []
    for raw in SUMS.read_bytes().splitlines():
        if DIRECTIVE.match(raw):
            continue
        m = ENTRY.match(raw)
        if m:
            recorded.append((m.group(1).decode().upper(),
                             m.group(2).decode("utf-8").lstrip("./")))

    want_by_path = {rel: want for want, rel in recorded}
    paths = list(want_by_path)

    # Every commit, not only the ones that touched each path: a commit can hold
    # the recorded bytes without having introduced them, and the release is a
    # tree, not a diff. Blob contents are cached by object id, so history is
    # walked once and each distinct version of a file is hashed once.
    commits = git("rev-list", "--all").decode().split()
    print(f"{len(commits)} commits, {len(paths)} recorded artifacts\n")

    digest_of: dict[str, str] = {}
    matches_at: dict[str, set[str]] = defaultdict(set)

    for sha in commits:
        try:
            tree = git("ls-tree", "-r", sha, "--", *paths).decode()
        except RuntimeError:
            continue
        for line in tree.splitlines():
            meta, _, rel = line.partition("\t")
            parts = meta.split()
            if len(parts) < 3 or parts[1] != "blob":
                continue
            blob = parts[2]
            if blob not in digest_of:
                digest_of[blob] = crlf_digest(git("cat-file", "blob", blob))
            if digest_of[blob] == want_by_path.get(rel):
                matches_at[rel].add(sha)

    for rel in paths:
        hits = matches_at.get(rel, set())
        if hits:
            print(f"found    {rel}  in {len(hits)} commit(s)")
        else:
            print(f"NOWHERE  {rel}")

    complete = [sha for sha in commits
                if all(sha in matches_at.get(rel, set()) for rel in paths)]
    print()
    if complete:
        newest = complete[0]
        print("A commit holds every recorded artifact:")
        print("  " + git("show", "-s", "--format=%ad %H %s", "--date=short",
                         newest).decode().strip())
        if len(complete) > 1:
            print(f"  and {len(complete) - 1} later commit(s) that change none of them")
        print("\nThat commit is the release. Move the tag onto it:")
        print(f"  git tag -f -a SECRAG-RRF40-2026-08-17 {newest[:9]}")
        return 0

    missing = [rel for rel in paths if not matches_at.get(rel)]
    if missing:
        print("No commit holds these bytes at all:")
        for rel in missing:
            print(f"  {rel}")
        print(
            "\nThe frozen release describes a working tree that was never\n"
            "committed. The hashes remain evidence of what was measured, and the\n"
            "code that produced the published figures is not recoverable from\n"
            "this repository at those exact bytes. Say so, in the manifest\n"
            "addendum and in the README, rather than moving a tag until\n"
            "something passes."
        )
    else:
        print(
            "Every artifact is found, but no single commit holds all of them.\n"
            "The release was hashed across a working tree that spanned commits.\n"
            "Record which commit each artifact came from."
        )
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
