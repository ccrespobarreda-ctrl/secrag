#!/usr/bin/env python3
"""
Declare which nineteen filings the corpus is built from, and check it.

    python src/pin_corpus.py --write      # from data/manifest.json
    python src/pin_corpus.py --verify     # the live corpus against the pin

WHY

`src/edgar.py` fetches the *latest* 10-K per ticker, so the corpus moves with
the SEC's calendar and with whatever the parser happened to produce that day.
The release measured 4,169 chunks; this pipeline now yields 4,124, and 23 gold
labels stopped holding because 45 chunks fewer upstream shifts every index after
them. That is finding 15, and its root cause is that nothing ever said which
documents the figures were measured over.

Accession numbers are immutable. Once they are written down, the corpus can be
rebuilt exactly -- and a corpus that has drifted can be told apart from one that
has not, which is the difference between a figure that reproduces and a figure
that used to.

WHAT IS DECLARED, AND WHY EACH FIELD

  accession, document, cik   the filing, exactly. `edgar.py --pinned` fetches
                             these and never asks EDGAR what the latest is
  raw_chars                  a changed document is visible without downloading
  n_chunks, n_documents      what the pipeline should produce from them
  chunker settings           the chunk count is meaningless without the budget
                             and overlap that produced it. Declaring a count
                             while leaving its inputs implicit would be finding
                             10 with a different subject

WHAT THIS DOES NOT DO

It does not make the corpus reproducible on its own. `edgar.py` still downloads
the latest filing unless it is told to use this file, and this module cannot
verify the chunk count without a database, so continuous integration -- which
has no corpus -- can only check that the pin and the manifest agree. Both gaps
are named in the README rather than left for a reader to discover, because a
check that covers less than it appears to is the defect this repository exists
to document.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "eval" / "corpus_expected.yaml"
MANIFEST = ROOT / "data" / "manifest.json"

log = logging.getLogger("pin")

FIELDS = ("ticker", "cik", "accession", "document", "filed_date",
          "report_date", "fiscal_year", "company", "raw_chars")


def load_manifest() -> list[dict]:
    if not MANIFEST.is_file():
        raise SystemExit(f"{MANIFEST} not found. Run src/edgar.py first.")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def corpus_counts() -> dict:
    """Chunk and document counts, or an honest absence."""
    if not os.environ.get("DATABASE_URL"):
        return {}
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute("select count(*) from chunks")
        chunks = cur.fetchone()[0]
        cur.execute("select count(*) from documents")
        docs = cur.fetchone()[0]
        conn.close()
        return {"n_chunks": chunks, "n_documents": docs}
    except Exception as exc:
        log.warning("corpus counts unavailable: %s", type(exc).__name__)
        return {}


def write() -> int:
    import yaml

    manifest = load_manifest()
    counts = corpus_counts()
    if not counts:
        log.error("No corpus counts available. Set DATABASE_URL and load the "
                  "corpus first: a pin without them declares the documents and "
                  "not what they should produce.")
        return 2

    filings = [{k: f.get(k) for k in FIELDS} for f in
               sorted(manifest, key=lambda f: f["ticker"])]

    header = f"""\
# Which filings this corpus is built from, and what they should produce.
#
# Accession numbers are immutable, so this file is what makes the corpus
# reproducible. src/edgar.py --pinned fetches exactly these and never asks EDGAR
# for the latest; src/pin_corpus.py --verify compares the live corpus against
# them.
#
# Written by src/pin_corpus.py --write. Do not edit by hand: a pin edited to
# match a corpus that drifted is the corpus declaring itself correct, which is
# the failure recorded as finding 15.
#
# The chunker settings are here because the chunk count cannot be checked
# without them. 4,169 and {counts['n_chunks']} are both correct counts of
# different corpora, and the difference is why 23 gold labels stopped holding.
version: 1
"""
    body = yaml.safe_dump({
        "corpus": {
            **counts,
            "chunk_tokens": C.CHUNK_TOKENS,
            "chunk_overlap_tokens": C.CHUNK_OVERLAP_TOKENS,
            "min_chunk_tokens": C.MIN_CHUNK_TOKENS,
        },
        "filings": filings,
    }, sort_keys=False, allow_unicode=True, default_flow_style=False)

    PIN.parent.mkdir(parents=True, exist_ok=True)
    PIN.write_text(header + body, encoding="utf-8")
    print(f"{len(filings)} filings, {counts['n_chunks']} chunks, "
          f"{counts['n_documents']} documents")
    print(f"wrote {PIN.relative_to(ROOT).as_posix()}")
    print("\nThis declares the corpus. It does not yet pin the download: "
          "src/edgar.py\nfetches the latest filing unless given --pinned.")
    return 0


def verify() -> int:
    import yaml

    if not PIN.is_file():
        print(f"{PIN.relative_to(ROOT).as_posix()} not found. "
              f"Write it first: python src/pin_corpus.py --write")
        return 2

    pin = yaml.safe_load(PIN.read_text(encoding="utf-8"))
    expected = {f["ticker"]: f for f in pin["filings"]}
    declared = pin.get("corpus", {})
    problems = []

    manifest = {f["ticker"]: f for f in load_manifest()}
    print(f"{len(expected)} filings declared, {len(manifest)} in the manifest")

    for ticker, want in sorted(expected.items()):
        have = manifest.get(ticker)
        if have is None:
            problems.append(f"{ticker}: declared and absent from the manifest")
            continue
        for field in ("accession", "document", "raw_chars"):
            if str(have.get(field)) != str(want.get(field)):
                problems.append(
                    f"{ticker}: {field} is {have.get(field)!r}, "
                    f"declared {want.get(field)!r}")

    for ticker in sorted(set(manifest) - set(expected)):
        problems.append(f"{ticker}: in the manifest and not declared")

    # The chunker first: a count that disagrees means nothing until the settings
    # that produce it are known to match.
    for key, live in (("chunk_tokens", C.CHUNK_TOKENS),
                      ("chunk_overlap_tokens", C.CHUNK_OVERLAP_TOKENS),
                      ("min_chunk_tokens", C.MIN_CHUNK_TOKENS)):
        if key in declared and declared[key] != live:
            problems.append(f"{key} is {live}, declared {declared[key]} — the "
                            f"chunk count below cannot be compared until this "
                            f"matches")

    counts = corpus_counts()
    if counts:
        for key in ("n_chunks", "n_documents"):
            if key in declared and counts.get(key) != declared[key]:
                problems.append(f"{key} is {counts[key]}, declared "
                                f"{declared[key]}")
        print(f"corpus: {counts['n_chunks']} chunks in "
              f"{counts['n_documents']} documents")
    else:
        print("corpus: not checked — no database. The filings above were "
              "checked\n  against the manifest, which is all continuous "
              "integration can do.")

    if problems:
        print(f"\n{len(problems)} discrepancy(ies):")
        for p in problems:
            print(f"  {p}")
        print(
            "\nThe corpus is not the one the published figures were measured\n"
            "over. Do not repair this by rewriting the pin. Either restore the\n"
            "declared filings with `python src/edgar.py --pinned`, or measure\n"
            "again and publish the new figures as new figures, the way\n"
            "docs/relabel-log.md did."
        )
        return 1

    print("\nThe corpus matches what was declared.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pin and verify the corpus")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return write() if args.write else verify()


if __name__ == "__main__":
    raise SystemExit(main())
