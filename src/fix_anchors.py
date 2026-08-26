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

WHAT IS PROPOSED, AND WHY IT IS AN EXTENSION

An earlier version searched the chunk for any unique span and offered that. It
was wrong on every hard case, because uniqueness is easy to optimise for and is
not what an anchor is for: it proposed the auditor's signature as the anchor for
a question about gross profit.

The anchors flagged here are not wrong. They are incomplete. "4,966,370" is the
answer; "Wayfair" sits inside the right passage; "2025" is a fragment of the
right sentence. What each needs is its own surroundings, not a replacement.

So the proposal grows the existing anchor outward inside its chunk, one word at
a time, keeping whatever was already chosen and stopping as soon as the result
matches a single chunk. The reviewer reads an extension of their own text rather
than a stranger's suggestion, which is a much shorter thing to check.

Extensions are still proposals. Nothing is written until `accept: true`, and
what is written is re-checked against the corpus first.

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


_DOC_CACHE: dict[str, list[str]] = {}


def _flat(text: str) -> str:
    """Collapse every run of whitespace, the way a reader sees the text."""
    return " ".join(text.split())


def document_chunks(cur, doc_id: str) -> list[str]:
    """
    Every chunk of a document, whitespace-flattened, loaded once.

    Two reasons, and the first is correctness. The raw text carries the line
    breaks of a filing's tables: "Old Navy Global 3 %" is stored with newlines
    between the cells. Anything read off a printed chunk has single spaces, so
    comparing it against the raw column finds nothing, and reports an anchor
    that is plainly there as matching zero chunks. Both sides are flattened
    before comparing.

    The second is speed. Growing an anchor word by word asked the database once
    per step; a document is four hundred kilobytes and fits in memory, so the
    whole search now runs without a round trip.
    """
    if doc_id not in _DOC_CACHE:
        cur.execute("select content from chunks where doc_id = %s "
                    "order by chunk_index", (doc_id,))
        _DOC_CACHE[doc_id] = [_flat(r[0]) for r in cur.fetchall()]
    return _DOC_CACHE[doc_id]


def count_in_document(cur, doc_id: str, needle: str) -> int:
    """How many chunks contain this text, comparing flattened to flattened."""
    n = _flat(needle).lower()
    if not n:
        return 0
    return sum(1 for c in document_chunks(cur, doc_id) if n in c.lower())


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


def _grow_from(cur, doc_id: str, body: str, starts: list[int], pos: int,
               anchor: str, max_words: int) -> tuple[str, int]:
    """Grow one occurrence outward, taking whichever side narrows it faster."""
    left = max([i for i in starts if i <= pos], default=0)
    right = pos + len(anchor)
    best = body[left:right]
    n = count_in_document(cur, doc_id, best)

    for _ in range(max_words):
        if n <= 1:
            break
        cands = []
        prev = max([i for i in starts if i < left], default=None)
        if prev is not None:
            cands.append((body[prev:right], prev, right))
        nxt = next((i for i in starts if i > right), None)
        if nxt is not None:
            grown = body[left:nxt].rstrip()
            cands.append((grown, left, left + len(grown)))
        if not cands:
            break
        scored = sorted((count_in_document(cur, doc_id, c[0]), c)
                        for c in cands)
        n, (best, left, right) = scored[0]

    return best.strip(), n


def extend_anchor(cur, doc_id: str, idx: int, anchor: str,
                  max_words: int = 20, max_occurrences: int = 6):
    """
    Grow an anchor outward inside its chunk until it identifies one chunk.

    Both directions are tried at each step and the better one kept. Growing
    only rightward would fail on a bare figure whose distinguishing row label
    sits to its left.

    Several starting points, not one. An anchor like "2025" occurs dozens of
    times inside a single chunk, and the first occurrence is usually the least
    distinctive — a page header or a column heading. An earlier version grew
    from that one and reported the anchor as unfixable when a later occurrence
    would have narrowed in two words.

    Returns the best result found, with its match count. A count that stays
    high means no window of this size around any occurrence is unique; why is a
    question about the chunk, and reading it is the way to answer that rather
    than assuming.
    """
    body = " ".join((chunk_text(cur, doc_id, idx) or "").split())
    if not body:
        return anchor, 0
    low, needle = body.lower(), anchor.lower()
    starts = [0] + [m.end() for m in re.finditer(r"\s", body)]

    positions, at = [], low.find(needle)
    while at >= 0 and len(positions) < max_occurrences:
        positions.append(at)
        at = low.find(needle, at + 1)
    if not positions:
        return anchor, 0

    best, best_n = anchor, 10 ** 6
    for pos in positions:
        span, n = _grow_from(cur, doc_id, body, starts, pos, anchor, max_words)
        if n and n < best_n:
            best, best_n = span, n
        if best_n <= 1:
            break
    return best, best_n


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
            grown, grown_n = extend_anchor(cur, g["doc_id"],
                                           g["chunk_index"], anchor)
            entries.append({
                "id": q["id"], "doc_id": g["doc_id"],
                "chunk_index": g["chunk_index"],
                "question": q["question"],
                "gold_answer": q.get("gold_answer") or "",
                "current": anchor, "current_matches": n,
                "proposed": grown if grown_n and grown_n <= n else "",
                "proposed_matches": grown_n,
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
        "# `proposed` is your own anchor with its surroundings added, grown\n"
        "# word by word inside the same chunk until it matches one. Read it,\n"
        "# and set `accept: true` if it still marks the right passage.\n"
        "#\n"
        "# Edit it freely. Anything written here is re-checked against the\n"
        "# corpus before it is applied: it must be present in the chunk it\n"
        "# labels, and match no more than eight chunks of the document.\n"
        "#\n"
        "# Entries left at accept: false are ignored.\n")
    out.write_text(header + yaml.safe_dump(entries, sort_keys=False,
                                           allow_unicode=True, width=200),
                   encoding="utf-8")
    print(f"{len(entries)} anchors matching more than {threshold} chunks"
          f"\nwrote {out}\n")
    fixed = sum(1 for e in entries if e["proposed"]
                and e["proposed_matches"] <= 1)
    partial = sum(1 for e in entries if e["proposed"]
                  and 1 < e["proposed_matches"] <= 8)
    stuck = [e for e in entries if not e["proposed"]
             or e["proposed_matches"] > 8]
    print(f"  {fixed:>3} extend to a single chunk")
    print(f"  {partial:>3} extend to within the threshold")
    print(f"  {len(stuck):>3} do not narrow enough. No window of up to twenty "
          f"words around any\n      occurrence is distinctive; read the chunk "
          f"before assuming why")
    for e in stuck:
        print(f"      {e['id']:<7} {e['doc_id']:<18} {e['current'][:28]!r}")
    print("\nRead each proposal before accepting it. An extension is short to "
          "check\nbecause it still contains the anchor you chose.")
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
        elif _flat(span).lower() not in _flat(text).lower():
            refused.append((e, "not present in the chunk it labels"))
        else:
            n = count_in_document(cur, e["doc_id"], span)
            if n == 0:
                refused.append((e, "matches no chunk of the document — the "
                                   "text is not there as written"))
            elif n <= 8:
                ok.append(e)
            else:
                refused.append((e, f"matches {n} chunks, still too many to "
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
          "--max-anchor-matches 8")
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
