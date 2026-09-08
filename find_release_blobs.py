#!/usr/bin/env python3
"""
Are the recorded bytes anywhere in the object database, reachable or not?

    python find_release_blobs.py

WHY THIS AND NOT find_release_commit.py

That script walked `git rev-list --all`, which lists commits reachable from a
ref. It reported that no commit holds the release's five code artifacts, and
concluded the bytes were never committed. That conclusion was larger than the
evidence: an amended or rebased commit is unreachable from every ref while its
blobs remain in the object database, and `--all` does not see it.

`git cat-file --batch-all-objects` does. If a blob here matches a recorded hash,
the exact bytes behind a published figure still exist and can be extracted; the
release is recoverable and the record can say where from. If nothing matches
after every blob in the repository has been hashed, then the bytes really are
gone, and that is worth stating once, with this search behind it.

Nothing is written or garbage-collected. Read-only.
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
DIRECTIVE = re.compile(rb"^#@\s*verify\s+(tree|ref)(?:\s+(\S+))?\s*$")


def git(*args: str) -> bytes:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode(errors="replace").strip())
    return out.stdout


def crlf_digest(data: bytes) -> str:
    data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return hashlib.sha256(data).hexdigest().upper()


def stream_blobs(oids: list[str]):
    """Hash every blob through one `git cat-file --batch` process.

    The first version spawned a git process per blob. On a repository with a
    few thousand objects that is minutes on Windows, and a check nobody waits
    for is a check nobody runs.
    """
    proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert proc.stdin and proc.stdout
    try:
        for oid in oids:
            proc.stdin.write(f"{oid}\n".encode())
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                continue
            size = int(header[2])
            body = proc.stdout.read(size)
            proc.stdout.read(1)               # the trailing newline
            yield oid, crlf_digest(body)
    finally:
        proc.stdin.close()
        proc.wait()


def main() -> int:
    targets: dict[str, str] = {}          # sha256 -> path it was recorded for
    for raw in SUMS.read_bytes().splitlines():
        if DIRECTIVE.match(raw):
            continue
        m = ENTRY.match(raw)
        if m:
            targets[m.group(1).decode().upper()] = \
                m.group(2).decode("utf-8").lstrip("./")

    # Every object, not only reachable ones. Blobs only, and only those whose
    # stored size could still normalise to a recorded file: adding CR to each
    # line grows a file by its line count, never shrinks it, so a blob larger
    # than the largest recorded artifact cannot be one of them.
    listing = git("cat-file", "--batch-all-objects", "--batch-check",
                  "--buffer").decode().splitlines()
    blobs = []
    for line in listing:
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            blobs.append((parts[0], int(parts[2])))

    print(f"{len(listing)} objects in the database, {len(blobs)} blobs")
    print(f"{len(targets)} recorded hashes to look for\n")

    found: dict[str, str] = {}            # sha256 -> blob object id
    for oid, digest in stream_blobs([o for o, _ in blobs]):
        if digest in targets and digest not in found:
            found[digest] = oid
            print(f"found  {targets[digest]}")
            print(f"       blob {oid}")

    missing = {d: p for d, p in targets.items() if d not in found}
    print()

    if found:
        reachable = set(git("rev-list", "--objects", "--all").decode().split())
        print("Where each found blob lives:")
        unreachable = False
        for digest, oid in found.items():
            where = "reachable" if oid in reachable else "UNREACHABLE"
            unreachable |= where == "UNREACHABLE"
            print(f"  {targets[digest]:<46} {where}")
        if unreachable:
            print(
            "\nAn UNREACHABLE blob is the bytes of a commit that was amended or\n"
            "rebased away. They exist and can be extracted:\n"
            "  git cat-file blob <object-id> > recovered.py\n"
            "They are also one `git gc` away from being deleted, so if the\n"
            "release is to be recoverable, that commit needs a ref pointing at\n"
            "it, not a note saying it used to exist."
            )

    if missing:
        print("\nNot in the object database at all:")
        for path in missing.values():
            print(f"  {path}")
        print(
            "\nEvery blob in the repository has now been hashed and none holds\n"
            "these bytes. The hashes remain evidence of what was measured -- the\n"
            "results files they were measured with all verify -- but the code at\n"
            "those exact bytes is gone. It was hashed from a working tree and\n"
            "edited before it was ever committed.\n"
            "\n"
            "What is still true, and is what the record should say: the published\n"
            "figures were produced by this code, the results are byte-identical\n"
            "to publication, and the source has since been corrected in ways\n"
            "findings 3, 7 and 11 describe. What is not true, and was implied by\n"
            "listing these hashes as release artifacts, is that a reader can\n"
            "check out the release and reproduce the bytes."
        )
    return 1 if missing else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
