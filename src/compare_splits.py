#!/usr/bin/env python3
"""
Compare retrieval across splits, and quantify the construction bias.

    python src/compare_splits.py
    python src/compare_splits.py --results-dir eval/results

WHAT THIS MEASURES, AND WHY IT IS NOT A LEADERBOARD

The three splits were not built the same way. The legacy questions were written
first and labeled by reading the filings; the newer ones were labeled with
find_gold.py --expect, which locates the answer string in the corpus with ilike,
independently of ranking. Keeping only questions whose evidence was locatable
that way selects for questions a lexical search can already find.

So a higher Recall@k on a newer split is not a better system. The diagnostic
below separates the two:

    lift = Recall(hybrid+company) - Recall(keyword alone)

Keyword alone is Postgres full-text search: close to what --expect does when it
picks a label. Where the labels were chosen by literal matching, keyword alone
already scores near the ceiling and the lift collapses toward zero. Where they
were not, the lift is what the retrieval system actually contributes.

A split with a high score and no lift is measuring its own labeling method.

THE CONTROL

multi_chunk questions resist the bias: their evidence is spread across several
chunks, so no single literal match captures it. If the splits agree on
multi_chunk while diverging elsewhere, the divergence is an artifact of
labeling rather than a difference in the system -- and that is a testable claim
rather than an assertion, which is the point of printing it.

INTERVALS

Recall@k is a proportion of questions, so Wilson applies. Coverage is a mean of
per-question fractions and needs a bootstrap over per-question values, which the
harness does not store; it is printed without an interval and labeled as such
rather than given a bound this script cannot justify.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from math import sqrt
from pathlib import Path

import yaml

# Each split names the file with per-question detail first, and the original
# aggregate-only file as a fallback. The two agree on every aggregate; only the
# newer one supports a bootstrap or a per-question comparison.
SPLITS = [
    ("legacy", ["vnext_baseline_legacy_v2.json",
                "vnext_baseline_legacy.json"], "regression"),
    ("development", ["vnext_baseline_dev_v2.json",
                     "vnext_baseline_dev.json"], "development"),
    ("reg+dev", ["vnext_baseline_tuning_v2.json",
                 "vnext_baseline_tuning.json"], "regression+development"),
    ("holdout", ["vnext_holdout_retrieval_v2.json",
                 "vnext_holdout_retrieval.json"], "holdout"),
]

BEST = "hybrid+company"
BASE = "keyword"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / d), min(1.0, (centre + margin) / d)


def type_counts(questions, spec, split_expr: str) -> Counter:
    """How many answerable questions of each type a split holds."""
    names = [s.strip() for s in split_expr.split("+")]
    wanted = {qid for n in names for qid in spec.get(n, [])}
    return Counter(q["type"] for q in questions
                   if q["id"] in wanted and q.get("answerable"))


def load(results_dir: Path):
    out = []
    for label, filenames, split_expr in SPLITS:
        for filename in filenames:
            path = results_dir / filename
            if path.exists():
                out.append((label, json.loads(path.read_text(encoding="utf-8")),
                            split_expr))
                break
        else:
            print(f"  (no results file for {label}, skipped)")
    return out


def bootstrap_mean(values: list[float], reps: int = 10000,
                   seed: int = 0) -> tuple[float, float]:
    """
    Percentile bootstrap over per-question values.

    Coverage is a mean of fractions, not a proportion, so Wilson does not
    apply. Resampling questions with replacement is the honest way to put an
    interval on it. The seed is fixed so the published figure does not move
    between runs of the reporting script.
    """
    if not values:
        return 0.0, 1.0
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n
                   for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


def missed(strategy: dict) -> set[str]:
    """Question ids where no gold chunk reached the top k."""
    return {r["id"] for r in strategy.get("per_question", []) if not r["hit"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare retrieval across splits")
    ap.add_argument("--results-dir", type=Path, default=Path("eval/results"))
    ap.add_argument("--questions", type=Path,
                    default=Path("eval/questions_vnext.yaml"))
    ap.add_argument("--splits", type=Path,
                    default=Path("eval/vnext_splits.yaml"))
    args = ap.parse_args()

    for p in (args.questions, args.splits):
        if not p.exists():
            print(f"{p} not found. Run from the repository root.")
            return 2

    questions = yaml.safe_load(args.questions.read_text(encoding="utf-8"))
    spec = yaml.safe_load(args.splits.read_text(encoding="utf-8"))
    spec = {k: v for k, v in spec.items() if isinstance(v, list)}

    loaded = load(args.results_dir)
    if not loaded:
        print("No baseline files found.")
        return 1

    k = loaded[0][1].get("k", "?")

    # ── 1. the bias diagnostic ────────────────────────────────────────
    print(f"\nCONSTRUCTION BIAS  ·  what the retrieval system adds over lexical "
          f"search alone\n")
    print(f"  {'split':<14}{'n':>4}  {'keyword':>9}{'  ' + BEST:>18}"
          f"{'lift':>9}")
    print("  " + "-" * 56)
    for label, r, _ in loaded:
        n = r["answerable"]
        kw = r["strategies"][BASE]["recall_at_k"]
        best = r["strategies"][BEST]["recall_at_k"]
        print(f"  {label:<14}{n:>4}  {kw:>9.3f}{best:>18.3f}"
              f"{best - kw:>+9.3f}")
    print("\n  A lift near zero means lexical search alone already finds the "
          "labels,\n  which is what labeling by literal match produces. It is a "
          "property of\n  the questions, not of the system.")

    # ── 2. headline recall with intervals ─────────────────────────────
    print(f"\n\nRECALL@{k} · {BEST} · one observation per question\n")
    print(f"  {'split':<14}{'hits':>10}{'recall':>10}{'95% CI':>22}")
    print("  " + "-" * 56)
    for label, r, _ in loaded:
        n = r["answerable"]
        recall = r["strategies"][BEST]["recall_at_k"]
        hits = round(recall * n)
        lo, hi = wilson(hits, n)
        print(f"  {label:<14}{f'{hits}/{n}':>10}{recall:>10.3f}"
              f"{f'[{lo:.3f}, {hi:.3f}]':>22}")
    print("\n  reg+dev overlaps legacy and development by construction; it is "
          "shown\n  because the tuning baselines were measured on it, not as a "
          "third sample.")

    # ── 3. by type, with the control called out ───────────────────────
    print(f"\n\nBY QUESTION TYPE · {BEST}\n")
    types = ["extractive", "multi_chunk", "comparative"]
    print(f"  {'split':<14}" +
          "".join(f"{t:>26}" for t in types))
    print(f"  {'':<14}" + "".join(f"{'recall / coverage':>26}" for _ in types))
    print("  " + "-" * (14 + 26 * len(types)))
    for label, r, split_expr in loaded:
        counts = type_counts(questions, spec, split_expr)
        row = f"  {label:<14}"
        for t in types:
            s = r["strategies"][BEST]
            rec = s["recall_by_type"].get(t)
            cov = s["coverage_by_type"].get(t)
            n = counts.get(t, 0)
            cell = ("—" if rec is None
                    else f"{rec:.3f} / {cov:.3f}  (n={n})")
            row += f"{cell:>26}"
        print(row)

    legacy = next((r for l, r, _ in loaded if l == "legacy"), None)
    hold = next((r for l, r, _ in loaded if l == "holdout"), None)
    if legacy and hold:
        lc = legacy["strategies"][BEST]["coverage_by_type"].get("multi_chunk")
        hc = hold["strategies"][BEST]["coverage_by_type"].get("multi_chunk")
        if lc and hc:
            print(f"\n  CONTROL · multi_chunk coverage, legacy {lc:.3f} vs "
                  f"holdout {hc:.3f}, a gap of {abs(hc - lc):.3f}.")
            print("  multi_chunk is the type literal-match labeling captures "
                  "worst, because\n  the evidence is spread across chunks. The "
                  "splits agreeing here while\n  diverging elsewhere is what "
                  "makes the divergence a labeling artifact\n  rather than a "
                  "change in the system.")

    # ── 4. coverage with a bootstrap interval ─────────────────────────
    have_detail = [(l, r) for l, r, _ in loaded
                   if r["strategies"][BEST].get("per_question")]
    if have_detail:
        print(f"\n\nCOVERAGE · {BEST} · percentile bootstrap over questions\n")
        print(f"  {'split':<14}{'n':>4}{'coverage':>11}{'95% CI':>22}")
        print("  " + "-" * 51)
        for label, r in have_detail:
            vals = [q["coverage"] for q in r["strategies"][BEST]["per_question"]]
            lo, hi = bootstrap_mean(vals)
            print(f"  {label:<14}{len(vals):>4}{sum(vals) / len(vals):>11.3f}"
                  f"{f'[{lo:.3f}, {hi:.3f}]':>22}")
        print("\n  These intervals are wide because the samples are small. That "
              "is the\n  finding, not a defect in the estimate.")

    # ── 5. do two strategies with the same score fail the same way? ───
    if have_detail:
        print(f"\n\nSAME SCORE, SAME QUESTIONS?  {BASE} vs {BEST}\n")
        for label, r in have_detail:
            a, b = r["strategies"][BASE], r["strategies"][BEST]
            ma, mb = missed(a), missed(b)
            same = "identical" if ma == mb else "DIFFERENT questions"
            print(f"  {label:<14}{BASE} misses {sorted(ma) or 'none'}")
            print(f"  {'':<14}{BEST} misses {sorted(mb) or 'none'}   -> {same}")
            if a["recall_at_k"] == b["recall_at_k"] and ma != mb:
                print(f"  {'':<14}Equal recall over different questions: the two "
                      f"paths are not\n  {'':<14}interchangeable, and 'adds "
                      f"nothing' holds only in aggregate.")
            print()

    print("\n  Coverage intervals come from the per-question records added to "
          "the\n  harness; splits without them are reported as aggregates only.")
    print("\n  Recall and coverage are comparable across splits only within a "
          "type.\n  The splits hold different mixes, so an aggregate comparison "
          "compares\n  mixes rather than systems.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
