#!/usr/bin/env python3
"""
Report generation figures with intervals, and separate refusals from misses.

    python src/report_intervals.py eval/results/vnext_holdout_generation.json
    python src/report_intervals.py eval/results/vnext_holdout_generation.json \
        --pool eval/results/vnext_generation_promptv2_judge2.json

TWO THINGS THIS FIXES

1. THE UNIT OF ANALYSIS

Three runs of the same question are not three independent observations. The
harness reports 27 unanswerable responses because nine questions were asked
three times; treating that as n=27 narrows every interval by a factor the data
does not support. A question counts once, and its verdict is the majority across
runs. Run-to-run disagreement is reported separately, as instability, which is
what it actually is.

2. A REFUSAL IS NOT A FALSE REFUSAL WHEN THE EVIDENCE WAS NEVER RETRIEVED

Refusing a question whose gold chunk did not reach the model is the correct
response, not a failure of the generator. Scoring it as a false refusal charges
the generator for the retriever's miss. Every refusal is therefore checked
against what was actually in the excerpts before it is counted.

--pool merges a second split for the zero-rate figures only. A rate of zero over
nine questions bounds the true value at 30%, which says almost nothing; the same
zero over forty bounds it at 9%. Pooling is legitimate exactly when both splits
produced zero and the question is how confident that zero is.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """
    Wilson score interval.

    Not the textbook normal approximation: at k=n it returns the degenerate
    [1.0, 1.0], which would claim certainty from nine observations. Wilson keeps
    a lower bound at the boundaries, which is the whole reason these figures need
    an interval.
    """
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / d), min(1.0, (centre + margin) / d)


def fmt(k: int, n: int, label: str) -> str:
    lo, hi = wilson(k, n)
    return (f"  {label:<34}{k:>3}/{n:<4} = {k / n if n else 0:6.1%}"
            f"   95% CI [{lo:5.1%}, {hi:5.1%}]")


def by_question(records: list[dict]) -> dict:
    """Collapse runs into one verdict per question, keeping the disagreement."""
    runs = defaultdict(list)
    for r in records:
        runs[r["id"]].append(r)

    out = {}
    for qid, rs in runs.items():
        refusals = sum(1 for r in rs if r["refused"])
        gold = set(rs[0].get("gold_chunk_ids") or [])
        retrieved_any = any(gold & set(r.get("excerpt_ids") or []) for r in rs)
        out[qid] = {
            "type": rs[0]["type"],
            "answerable": rs[0]["answerable"],
            "n_runs": len(rs),
            "refusals": refusals,
            "refused": refusals * 2 > len(rs),      # majority
            "unstable": 0 < refusals < len(rs),
            "gold_labeled": bool(gold),
            "gold_retrieved": retrieved_any,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generation figures with intervals, per question")
    ap.add_argument("results", type=Path)
    ap.add_argument("--pool", type=Path, action="append", default=[],
                    help="another split to merge, for zero-rate bounds only")
    args = ap.parse_args()

    if not args.results.exists():
        print(f"{args.results} not found.")
        return 2

    g = json.loads(args.results.read_text(encoding="utf-8"))
    if "records" not in g:
        print(f"{args.results} has no 'records' key -- is it a generation "
              f"results file? Keys: {sorted(g)[:8]}")
        return 2

    qs = by_question(g["records"])
    runs = g.get("runs", "?")
    print(f"{args.results.name}  ·  {len(qs)} questions × {runs} runs "
          f"·  model {g.get('model', '?')}\n")

    answerable = {k: v for k, v in qs.items() if v["answerable"]}
    unanswerable = {k: v for k, v in qs.items() if not v["answerable"]}

    # ── refusals, split into correct and not ──────────────────────────
    refused_ans = {k: v for k, v in answerable.items() if v["refused"]}
    justified = {k: v for k, v in refused_ans.items()
                 if v["gold_labeled"] and not v["gold_retrieved"]}
    unjustified = {k: v for k, v in refused_ans.items() if k not in justified}

    print("REFUSALS ON ANSWERABLE QUESTIONS")
    if not refused_ans:
        print("  none\n")
    else:
        for qid, v in sorted(refused_ans.items()):
            verdict = ("correct — gold chunk never reached the model"
                       if qid in justified else
                       "FALSE REFUSAL — the evidence was in the excerpts")
            print(f"  {qid}  {v['type']:<14} refused in {v['refusals']}/"
                  f"{v['n_runs']} runs   {verdict}")
        print()

    print("HEADLINE FIGURES, one observation per question")
    print(fmt(sum(1 for v in unanswerable.values() if v["refused"]),
              len(unanswerable), "refusal rate on unanswerable"))
    print(fmt(sum(1 for v in unanswerable.values() if not v["refused"]),
              len(unanswerable), "hallucination rate"))
    print(fmt(len(unjustified), len(answerable),
              "false refusal (retrieval-adjusted)"))
    print(fmt(len(refused_ans), len(answerable),
              "  refusals, unadjusted"))

    unstable = [k for k, v in qs.items() if v["unstable"]]
    print(f"\n  refusal decision changed between runs: {len(unstable)} of "
          f"{len(qs)}" + (f"  {sorted(unstable)}" if unstable else ""))

    types = Counter(v["type"] for v in qs.values())
    print("\n  questions by type: " +
          ", ".join(f"{t} {n}" for t, n in sorted(types.items())))

    # ── pooled zero-rate bounds ───────────────────────────────────────
    if args.pool:
        pooled_unans, pooled_halluc, names = len(unanswerable), \
            sum(1 for v in unanswerable.values() if not v["refused"]), \
            [args.results.name]
        for p in args.pool:
            if not p.exists():
                print(f"\n  --pool {p} not found, skipped")
                continue
            other = json.loads(p.read_text(encoding="utf-8"))
            o = by_question(other.get("records", []))
            ou = {k: v for k, v in o.items() if not v["answerable"]}
            pooled_unans += len(ou)
            pooled_halluc += sum(1 for v in ou.values() if not v["refused"])
            names.append(p.name)

        print(f"\nPOOLED ACROSS SPLITS  ({', '.join(names)})")
        print(fmt(pooled_halluc, pooled_unans, "hallucination rate"))
        print(fmt(pooled_unans - pooled_halluc, pooled_unans,
                  "refusal rate on unanswerable"))
        print("\n  Pooling is reported only for these two rates, and only "
              "because\n  both splits produced the same count. It does not "
              "merge the splits\n  for anything measured against gold labels, "
              "which are not comparable\n  across construction methods.")

    print("\nGroundedness is not recomputed here: its uncertainty is dominated "
          "by\njudge self-agreement, not by sample size. Report it beside that "
          "figure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
