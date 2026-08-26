#!/usr/bin/env python3
"""
Strengthen weak gold anchors, in two phases with a person in between.

    python src/fix_anchors.py --review eval/anchor_review.yaml
    # ...read it, set accept: true on the ones you agree with...
    python src/fix_anchors.py --apply eval/anchor_review.yaml --dry-run
    python src/fix_anchors.py --apply eval/anchor_review.yaml

WHAT AN ANCHOR HAS TO DO

The invariant is not "the anchor must be unique". It is that the anchor must be
able to fail when the label stops holding, and there are two ways to manage
that. An anchor that carries the answer fails if the chunk loses the figure. An
anchor unique in its document fails if the label drifts. Either is enough, and
"6,165,376" cannot be unique because the same total appears in the income
statement, the segment note and the MD&A of one filing.

WHAT THIS DOES NOT DO ANY MORE

An earlier version searched each chunk for a unique span and proposed it as a
replacement. On the fourteen hardest anchors it got fourteen out of fourteen
wrong: text that was unique and irrelevant, offering the auditor's signature as
the anchor for a question about gross profit. Uniqueness is easy to optimise for
and is not what an anchor is for.

The proposals are gone. Phase one writes the question, the labelled answer and
the text of the chunk, and leaves the anchor blank. There are 127 labels here;
reading the handful that need attention is an afternoon, and it is the part no
tool should be doing.

Phase two checks what was written — present in the chunk, and either unique or
carrying the answer — and applies it.

WHY THE YAML IS EDITED AS TEXT

Round-tripping eval/questions_vnext.yaml through PyYAML reflows 185 lines of
long strings without changing a single value. The anchor edits would be buried
in that noise and the diff would be unreviewable. This replaces the specific
`contains:` lines and leaves every other byte alone.

WHAT IS CHECKED BEFORE ANYTHING IS WRITTEN

Each accepted anchor must be present in the chunk it labels, and must appear in
no other chunk of that document. An anchor that fails either test is refused and
reported, not written and warned about.

Nothing here touches recall, coverage or any published figure. Anchors take no
part in retrieval; they decide only whether the verifier is able to fail.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("fix_anchors")

_ID = re.compile(r"^- id:\s*(\S+)\s*$")
_DOC = re.compile(r"^\s+- doc_id:\s*(\S+)\s*$")
_IDX = re.compile(r"^\s+chunk_index:\s*(\d+)\s*$")
_CONTAINS = re.compile(r"^(\s+)contains:\s*(.*)$")
_KEY = re.compile(r"^\s*-?\s*\w[\w_]*:")


def count_in_document(cur, doc_id: str, needle: str) -> int:
    cur.execute("""select count(*) from chunks
                   where doc_id = %s and content ilike %s""",
                (doc_id, f"%{needle}%"))
    return cur.fetchone()[0]


def chunk_text(cur, doc_id: str, idx: int) -> str | None:
    cur.execute("""select content from chunks
                   where doc_id = %s and chunk_index = %s""", (doc_id, idx))
    row = cur.fetchone()
    return row[0] if row else None


_STOP = {"the", "a", "an", "of", "and", "or", "in", "to", "for", "our", "we",
         "is", "are", "was", "were", "as", "at", "on", "by", "with", "that",
         "this", "its", "it", "from", "which", "their", "has", "have"}


def _norm(word: str) -> str:
    """A labelled answer writes "$6,165,376"; the filing writes "6,165,376"."""
    return word.strip("$\u20ac\u00a3.,;:()[]\"'").lower()


def answer_words(gold_answer: str | None) -> set[str]:
    """Content words of the answer. Figures are kept whatever their length."""
    if not gold_answer:
        return set()
    out = set()
    for raw in re.findall(r"[\w,\.%$\u20ac\u00a3]+", gold_answer):
        w = _norm(raw)
        if not w or w in _STOP:
            continue
        if any(c.isdigit() for c in w) or len(w) > 2:
            out.add(w)
    return out


def yaml_scalar(value: str) -> str:
    """
    Quote the way PyYAML would, so the file stays loadable.

    Dumped as a mapping value rather than a bare scalar: safe_dump of a lone
    string appends a "..." document-end marker that survives .strip() and lands
    in the middle of the file, which produces a YAML document that no longer
    parses. Caught by round-tripping the result during testing rather than by
    reading the code.
    """
    import yaml
    return yaml.safe_dump({"k": value}, default_flow_style=False,
                          allow_unicode=True, width=10_000).strip()[3:]


def do_review(cur, questions_path: Path, out: Path, threshold: int) -> int:
    import yaml
    questions = yaml.safe_load(questions_path.read_text(encoding="utf-8"))

    entries = []
    for q in questions:
        if not q.get("answerable"):
            continue
        answer = answer_words(q.get("gold_answer"))
        for g in (q.get("gold_chunks") or []):
            anchor = g.get("contains")
            if not anchor:
                continue
            n = count_in_document(cur, g["doc_id"], anchor)
            if n <= threshold:
                continue        # narrow enough to say which chunk it means
            body = " ".join((chunk_text(cur, g["doc_id"], g["chunk_index"])
                             or "").split())
            entries.append({
                "id": q["id"], "doc_id": g["doc_id"],
                "chunk_index": g["chunk_index"],
                "question": q["question"],
                "gold_answer": q.get("gold_answer") or "",
                "current": anchor, "current_matches": n,
                "chunk_text": body,
                "proposed": "",
                "accept": False,
            })

    header = (
        "# Anchor review. Generated by src/fix_anchors.py --review.\n"
        "#\n"
        "# Every entry is an anchor that matches too many chunks of its own\n"
        "# document to say which one it means, so it stays satisfied wherever\n"
        "# the label points.\n"
        "#\n"
        "# Read `question`, `gold_answer` and `chunk_text`, then write an\n"
        "# anchor into `proposed` and set `accept: true`.\n"
        "#\n"
        "# A good anchor matches one chunk, or few. Prefer text that also\n"
        "# carries the answer, so it fails if the chunk loses the figure too.\n"
        "#\n"
        "# Anything written here is checked before it is applied.\n"
        "#\n"
        "# Entries left at accept: false are ignored.\n")
    out.write_text(header + yaml.safe_dump(entries, sort_keys=False,
                                           allow_unicode=True, width=200),
                   encoding="utf-8")
    print(f"{len(entries)} anchors matching more than {threshold} chunks"
          f"\nwrote {out}")
    for e in entries:
        print(f"  {e['id']:<7} {e['doc_id']:<18} {e['current'][:30]!r} "
              f"in {e['current_matches']} chunks")
    if entries:
        print("\nEach needs an anchor written by hand. They are few on "
              "purpose: an anchor\nchosen by a tool is an anchor nobody read.")
    return 0


def do_apply(cur, questions_path: Path, review: Path, dry_run: bool) -> int:
    import yaml
    entries = [e for e in yaml.safe_load(review.read_text(encoding="utf-8"))
               if e.get("accept")]
    if not entries:
        print("Nothing accepted in the review file. Set accept: true first.")
        return 1

    print(f"{len(entries)} accepted\n")

    ok, refused = [], []
    for e in entries:
        span = (e.get("proposed") or "").strip()
        if not span:
            refused.append((e, "no anchor given"))
            continue
        text = chunk_text(cur, e["doc_id"], e["chunk_index"])
        if text is None:
            refused.append((e, "chunk not found"))
        elif span.lower() not in " ".join(text.split()).lower():
            refused.append((e, "not present in the chunk it labels"))
        else:
            n = count_in_document(cur, e["doc_id"], span)
            if n <= 8:
                ok.append(e)
            else:
                refused.append((e, f"matches {n} chunks — still too many to "
                                   f"identify one"))

    for e, why in refused:
        print(f"  REFUSED  {e['id']:<7} {e['doc_id']:<18} {why}")
    if refused:
        print()

    if not ok:
        print("Nothing to write.")
        return 1

    # Targeted line edit. A PyYAML round-trip reflows 185 lines of unrelated
    # long strings, and an anchor change buried in that is a change nobody can
    # review.
    lines = questions_path.read_text(encoding="utf-8").splitlines(keepends=True)
    wanted = {(e["id"], e["doc_id"], e["chunk_index"]): e for e in ok}

    out, qid, doc, idx, applied = [], None, None, None, []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _ID.match(line.rstrip("\n"))
        if m:
            qid, doc, idx = m.group(1), None, None
        elif _DOC.match(line.rstrip("\n")):
            doc = _DOC.match(line.rstrip("\n")).group(1)
            idx = None
        elif _IDX.match(line.rstrip("\n")):
            idx = int(_IDX.match(line.rstrip("\n")).group(1))

        cm = _CONTAINS.match(line.rstrip("\n"))
        if cm and (qid, doc, idx) in wanted:
            e = wanted.pop((qid, doc, idx))
            indent = cm.group(1)
            out.append(f"{indent}contains: {yaml_scalar(e['proposed'])}\n")
            applied.append(e)
            # Skip the wrapped continuation lines of the old value.
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and not _KEY.match(nxt) and \
                        len(nxt) - len(nxt.lstrip()) > len(indent):
                    i += 1
                    continue
                break
            continue

        out.append(line)
        i += 1

    for key in wanted:
        print(f"  NOT FOUND in the yaml: {key}")

    for e in applied:
        print(f"  {e['id']:<7} {e['current'][:26]!r} -> {e['proposed'][:44]!r}")

    if dry_run:
        print(f"\n{len(applied)} would be written to {questions_path}. "
              f"Nothing written.")
        return 0

    questions_path.write_text("".join(out), encoding="utf-8")
    print(f"\n{len(applied)} anchors rewritten in {questions_path}")
    print("\nNow regenerate the derived splits and re-verify:")
    print("  python src/derive_split.py --verify")
    print("  python src/verify_labels.py --questions eval/questions_vnext.yaml "
          "--max-anchor-matches 4")
    print("\nThe derived files carry copies of these anchors, so delete and "
          "rebuild them:\n  eval/questions_vnext_{regression,dev,tuning,"
          "holdout}.yaml")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Strengthen weak gold anchors")
    ap.add_argument("--questions", type=Path,
                    default=Path("eval/questions_vnext.yaml"))
    ap.add_argument("--review", type=Path, help="write a review file and stop")
    ap.add_argument("--apply", type=Path, help="apply the accepted entries")
    ap.add_argument("--threshold", type=int, default=8,
                    help="review anchors matching more chunks than this")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not (args.review or args.apply):
        ap.error("give --review or --apply")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    try:
        if args.review:
            return do_review(cur, args.questions, args.review, args.threshold)
        return do_apply(cur, args.questions, args.apply, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
