#!/usr/bin/env python3
"""
Does removing the other company's name improve retrieval for a comparative?

    python src/experiment_subquery.py
    python src/experiment_subquery.py --type comparative --deep 200

WHAT IS BEING TESTED

search() splits the budget between the companies a question names, and sends the
whole question to each of them. Searching Under Armour's filing for "Do both Nike
and Under Armour cite foreign currency exchange rates as a risk factor?" spends
part of the query on a term that cannot appear in the documents being searched:
no Under Armour passage says Nike. On the lexical side that is noise. On the
dense side the embedding of a two-company question points between them rather
than at either.

The variant strips the other companies' aliases from each sub-query, using the
alias table that already exists for detection. No model, no extra call, no cost.

WHY RANK AND NOT COVERAGE

There are five comparative questions in the labeled set. Coverage over five
questions moves in steps of 0.2 and cannot separate a real improvement from
noise -- a limit documented in docs/measurement-honesty.md, and a commitment not
to decide against that metric.

Rank does not have that problem. It is continuous, it is measured per gold chunk,
and a chunk moving from 79th to 9th is not a rounding artifact. So this reports
rank movement, which is diagnostic and honest at this sample size, and leaves
coverage to be confirmed later on an expanded set.

NOTHING HERE MODIFIES THE SYSTEM

This is a standalone comparison. src/retrieve.py is untouched until the numbers
justify touching it.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("subquery")


# Names used only for stripping, never for detection.
#
# The detection table holds the shortest alias that identifies a company, which
# is the right choice for finding one and the wrong choice for removing one:
# stripping "deckers" from "Deckers Outdoor" leaves "Outdoor", and stripping
# "abercrombie" from "Abercrombie & Fitch" leaves "& Fitch". Both fragments then
# travel into the other company's sub-query as noise, which is the problem this
# is meant to remove.
STRIP_EXTRA: dict[str, tuple[str, ...]] = {
    "DECK": ("deckers outdoor", "deckers brands"),
    "ANF":  ("abercrombie & fitch", "abercrombie and fitch"),
    "GAP":  ("the gap, inc", "the gap inc", "gap, inc"),
    "URBN": ("urban outfitters, inc",),
    "LEVI": ("levi strauss & co", "levi strauss and co"),
    "COLM": ("columbia sportswear company",),
    "HNST": ("the honest company",),
}


def strip_other_companies(question: str, keep: str, tickers: list[str]) -> str:
    """
    Remove every named company except `keep`, and tidy what the removal breaks.

    Longest form first, so "columbia sportswear" goes whole rather than leaving
    "sportswear" behind. COMPANY_PATTERNS is applied too: Gap is detected by a
    pattern rather than a literal, and skipping it would leave "Gap" sitting in
    Abercrombie's sub-query.

    The tidy-up matters more than it looks. "Do both and Under Armour cite ..."
    is not the same input to an encoder as "Do Under Armour cite ...", and the
    dangling conjunction is exactly the kind of thing that survives a naive
    replace and quietly degrades the embedding it was meant to improve.
    """
    out = question
    for ticker in tickers:
        if ticker == keep:
            continue
        names = set(R.COMPANY_ALIASES.get(ticker, ())) | set(
            STRIP_EXTRA.get(ticker, ()))
        for alias in sorted(names, key=len, reverse=True):
            out = re.sub(rf"\b{re.escape(alias)}\b", " ", out, flags=re.I)
        if ticker in R.COMPANY_PATTERNS:
            out = re.sub(R.COMPANY_PATTERNS[ticker], " ", out, flags=re.I)

    out = re.sub(r"\s*&\s*(?=\s|$|[,?.])", " ", out)
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r"\b(and|or|versus|vs\.?)\s+(and|or|versus|vs\.?)\b",
                 r"\1", out, flags=re.I)
    out = re.sub(r"\b(both|and|or|versus|vs\.?)\s*(?=[,?.]|$)", "", out,
                 flags=re.I)
    out = re.sub(r"\b(do|does)\s+both\b", r"\1", out, flags=re.I)
    out = re.sub(r"(^|\s)(and|or)\s+", r"\1", out, flags=re.I)
    return re.sub(r"\s{2,}", " ", out).strip(" ,")


def interleave(buckets: list[list], per: int, top_k: int) -> list:
    """The same round-robin search() uses, so only the query differs."""
    out, seen = [], set()
    for i in range(per):
        for bucket in buckets:
            if i < len(bucket) and bucket[i].chunk_id not in seen:
                seen.add(bucket[i].chunk_id)
                out.append(bucket[i])
    return out[:top_k]


def decomposed_search(cur, question: str, embed, tickers: list[str],
                      top_k: int) -> list:
    per = max(1, top_k // len(tickers))
    buckets = []
    for t in tickers:
        sub = strip_other_companies(question, t, tickers)
        buckets.append(R.search_hybrid(cur, sub, embed(sub),
                                       top_k=per, tickers=[t]))
    return interleave(buckets, per, top_k)


def rank_of(hits, chunk_id: int):
    for i, h in enumerate(hits, 1):
        if h.chunk_id == chunk_id:
            return i
    return None


def fmt(r, k: int) -> str:
    if r is None:
        return "  none"
    return f"{r:>4}{'*' if r <= k else ' '}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Per-company sub-queries for multi-company questions")
    ap.add_argument("--questions", type=Path,
                    default=Path("eval/questions_vnext_regression.yaml"))
    ap.add_argument("--type", default="comparative")
    ap.add_argument("-k", type=int, default=C.RETRIEVAL_TOP_K)
    ap.add_argument("--deep", type=int, default=200)
    ap.add_argument("--save", type=Path)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    import labels as L
    from search import embed_query

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    questions = L.load(args.questions)
    L.resolve(cur, questions)
    rows = [q for q in questions
            if q.get("answerable") and q.get("type") == args.type
            and q.get("gold_chunk_ids")]
    if not rows:
        print(f"No labeled {args.type} questions in {args.questions}.")
        return 1

    print(f"{len(rows)} {args.type} questions.  * = inside k={args.k}\n")
    print(f"  {'question':<8}{'gold':>8}{'ticker':>8}"
          f"{'current':>10}{'sub-query':>11}   change")
    print("  " + "-" * 62)

    detail, improved, worsened, same = [], 0, 0, 0
    hits_before = hits_after = 0

    for q in rows:
        tickers = R.detect_companies(q["question"])
        if len(tickers) < 2:
            continue

        base = R.search(cur, q["question"], embed_query(q["question"]),
                        top_k=args.deep)
        new = decomposed_search(cur, q["question"], embed_query, tickers,
                                args.deep)

        for cid in dict.fromkeys(q["gold_chunk_ids"]):
            cur.execute("""select d.ticker from chunks c
                           join documents d using (doc_id)
                           where c.chunk_id = %s""", (cid,))
            row = cur.fetchone()
            ticker = row[0] if row else "?"

            rb, ra = rank_of(base, cid), rank_of(new, cid)
            hits_before += 1 if rb and rb <= args.k else 0
            hits_after += 1 if ra and ra <= args.k else 0

            if rb is None and ra is None:
                verdict, tag = "both out of reach", same
                same += 1
            elif ra is None:
                verdict = "LOST"
                worsened += 1
            elif rb is None or ra < rb:
                verdict = "better"
                improved += 1
            elif ra > rb:
                verdict = "worse"
                worsened += 1
            else:
                verdict = "unchanged"
                same += 1

            print(f"  {q['id']:<8}{cid:>8}{ticker:>8}"
                  f"{fmt(rb, args.k)}{fmt(ra, args.k):>11}   {verdict}")
            detail.append({"id": q["id"], "chunk_id": cid, "ticker": ticker,
                           "rank_before": rb, "rank_after": ra})

        for t in tickers:
            print(f"           {t}: {strip_other_companies(q['question'], t, tickers)!r}")
        print()

    n = len(detail)
    print("=" * 66)
    print(f"{n} gold chunks\n")
    print(f"  rank improved{'':<14}{improved:>3}")
    print(f"  rank unchanged or both absent{'':<0}{same:>3}")
    print(f"  rank worsened or lost{'':<6}{worsened:>3}")
    print(f"\n  delivered inside k={args.k}:  {hits_before} -> {hits_after}"
          f"   (of {n})")
    print(f"\n  Rank movement is the evidence here. Coverage over "
          f"{len(rows)} questions\n  cannot resolve a change this size and is "
          f"not used to decide.")

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(
            {"type": args.type, "k": args.k, "deep": args.deep,
             "improved": improved, "worsened": worsened, "same": same,
             "delivered_before": hits_before, "delivered_after": hits_after,
             "chunks": detail}, indent=1), encoding="utf-8")
        print(f"\nSaved to {args.save}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
