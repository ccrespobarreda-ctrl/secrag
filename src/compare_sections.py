#!/usr/bin/env python3
"""
Did correcting the section boundaries produce better answers?

    python src/compare_sections.py

The paired comparison the rule of 11 September specifies, under the two
amendments that followed it. It reads six correctness files -- three runs of each
corpus -- and writes the comparison to eval/results/sections_comparison.json.

Read only. It opens no database and makes no API call.

HOW A QUESTION IS SCORED, AND WHY EACH CHOICE

  strict per run        CORRECT scores 1 and every other verdict scores 0, so a
                        question's rate over three runs lands in [0, 1/3, 2/3, 1].
                        That is what the rule states. PARTIALLY_CORRECT is not
                        half a point here: the rule decides on correctness
                        against the labelled answer, and a partial answer is not
                        that answer.

  JUDGE_ERROR excluded  Amendment 2, decision 1. A judge that returns no verdict
                        produced an observation that did not happen, not an
                        unfavourable one, so it is dropped from that question's
                        denominator rather than imputed. A question with no
                        legible verdict in any of its three runs is excluded from
                        the comparison and named. The counts are reported per
                        side, because a judge that fails more on one corpus than
                        the other is a fact about the experiment.

  REFUSED scores 0      A refusal is not a correct answer. It is reported
                        separately as well, because the rule treats refusal as a
                        guardrail rather than as part of the correctness figure,
                        and a question refused on both sides contributes nothing
                        to the paired difference either way.

  Q016 excluded         Amendment 1. Its verdict varied between identical calls,
                        and the exclusion was decided before either side was
                        measured. It is unanswerable, so it does not reach
                        correctness at all, and the exclusion is recorded here as
                        a no-op rather than dropped from the record.

THE INTERVAL

A percentile bootstrap over the per-question differences, resampling questions
rather than runs, because the questions are the sample and the runs are repeated
measurement of each one. 10,000 resamples, seeded, so the figure reproduces.

A sign test on the questions that moved is reported beside it. With a handful of
differences the bootstrap interval is wide and the sign test is blunt; both are
printed so that neither can be quoted alone.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"

EXCLUDED = {"Q016"}          # amendment 1, decided before either side was run
MISSING = {"JUDGE_ERROR", "NO_REFERENCE"}
RESAMPLES = 10_000
SEED = 20260918


def read_side(stem: str) -> tuple[dict[str, list[str]], list[dict]]:
    """Verdicts per question across the three runs, and the files they came from."""
    verdicts: dict[str, list[str]] = defaultdict(list)
    provenance = []
    for run in (0, 1, 2):
        path = RESULTS / f"{stem}_r{run}.json"
        if not path.is_file():
            raise SystemExit(f"{path} not found.")
        data = json.loads(path.read_text(encoding="utf-8"))
        provenance.append({
            "file": path.name,
            "run_judged": data.get("run_judged"),
            "judged_from": (data.get("judged_from") or {}).get("path"),
            "questions_sha256": (data.get("measured_against") or {}).get(
                "questions_sha256"),
            "n_chunks": (data.get("measured_against") or {}).get("n_chunks"),
        })
        for row in data["results"]:
            verdicts[row["id"]].append(row["verdict"])
    return dict(verdicts), provenance


def rate(verdicts: list[str]) -> float | None:
    """Share of legible runs that were CORRECT, or None if none were legible."""
    legible = [v for v in verdicts if v not in MISSING]
    if not legible:
        return None
    return sum(v == "CORRECT" for v in legible) / len(legible)


def bootstrap(diffs: list[float]) -> tuple[float, float]:
    rng = random.Random(SEED)
    n = len(diffs)
    means = []
    for _ in range(RESAMPLES):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return means[int(0.025 * RESAMPLES)], means[int(0.975 * RESAMPLES) - 1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Paired comparison of the two corpora")
    ap.add_argument("--before", default="correctness_sections_before")
    ap.add_argument("--after", default="correctness_sections_after")
    ap.add_argument("--out", default=RESULTS / "sections_comparison.json", type=Path)
    args = ap.parse_args()

    before, prov_before = read_side(args.before)
    after, prov_after = read_side(args.after)

    print("=" * 70)
    print("Does correcting the section boundaries produce better answers?")
    print("=" * 70)
    print("\nuncorrected corpus")
    for p in prov_before:
        print(f"  {p['file']:<42} {p['n_chunks']} chunks")
    print("corrected corpus")
    for p in prov_after:
        print(f"  {p['file']:<42} {p['n_chunks']} chunks")

    shared = sorted(set(before) & set(after))
    only_before = sorted(set(before) - set(after))
    only_after = sorted(set(after) - set(before))
    if only_before or only_after:
        print(f"\n  questions on one side only: {only_before + only_after}")
        print("  Not a paired comparison over those. They are excluded and named.")

    judge_errors = {
        "before": sum(v in MISSING for vs in before.values() for v in vs),
        "after": sum(v in MISSING for vs in after.values() for v in vs),
    }

    rows, excluded_no_verdict = [], []
    for qid in shared:
        if qid in EXCLUDED:
            continue
        rb, ra = rate(before[qid]), rate(after[qid])
        if rb is None or ra is None:
            excluded_no_verdict.append(qid)
            continue
        rows.append({
            "id": qid,
            "before": rb, "after": ra, "diff": ra - rb,
            "before_verdicts": before[qid], "after_verdicts": after[qid],
        })

    diffs = [r["diff"] for r in rows]
    n = len(diffs)
    mean_before = sum(r["before"] for r in rows) / n
    mean_after = sum(r["after"] for r in rows) / n
    mean_diff = sum(diffs) / n
    lo, hi = bootstrap(diffs)

    moved = [r for r in rows if r["diff"] != 0]
    up = [r for r in moved if r["diff"] > 0]
    down = [r for r in moved if r["diff"] < 0]

    print(f"\n{n} questions compared, paired\n")
    print(f"{'':<28}{'uncorrected':>14}{'corrected':>12}")
    print("-" * 54)
    print(f"{'correctness, mean of 3 runs':<28}{mean_before:>13.1%}{mean_after:>12.1%}")
    print(f"{'JUDGE_ERROR, total':<28}{judge_errors['before']:>13}"
          f"{judge_errors['after']:>12}")

    print(f"\npaired difference       {mean_diff:+.1%}")
    print(f"95% bootstrap interval  [{lo:+.1%}, {hi:+.1%}]"
          f"   {RESAMPLES:,} resamples, seed {SEED}")

    if lo <= 0 <= hi:
        verdict = (
            "The interval spans zero. Correcting the section boundaries does not\n"
            "measurably change answers at this sample size. That is the result.\n"
            "It is not read as support for whichever figure is higher, and the\n"
            "corrected corpus is adopted regardless, because the boundaries were\n"
            "wrong.")
    elif lo > 0:
        verdict = ("The corrected corpus leads by more than the interval. The\n"
                   "section boundaries were costing answers.")
    else:
        verdict = ("The corrected corpus is worse by more than the interval. It\n"
                   "is adopted anyway; reverting a correct parse because the\n"
                   "figures preferred the incorrect one is the one move this\n"
                   "project cannot make.")
    print(f"\n{verdict}")

    print(f"\nsign test: {len(up)} question(s) up, {len(down)} down, "
          f"{n - len(moved)} unchanged")

    if moved:
        print(f"\n{'=' * 70}\n{len(moved)} question(s) changed. Every one named:\n"
              f"{'=' * 70}")
        for r in sorted(moved, key=lambda r: -abs(r["diff"])):
            arrow = "better" if r["diff"] > 0 else "worse "
            print(f"\n  {r['id']}  {arrow}  {r['before']:.0%} -> {r['after']:.0%}")
            print(f"    uncorrected  {', '.join(r['before_verdicts'])}")
            print(f"    corrected    {', '.join(r['after_verdicts'])}")

    if excluded_no_verdict:
        print(f"\n{len(excluded_no_verdict)} question(s) had no legible verdict on "
              f"a side and are excluded: {excluded_no_verdict}")

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "rule": ["docs/decision-rule-sections.md",
                 "docs/decision-rule-sections-amendment-1.md",
                 "docs/decision-rule-sections-amendment-2.md"],
        "sources": {"uncorrected": prov_before, "corrected": prov_after},
        "scoring": ("CORRECT scores 1 per run, every other verdict 0; "
                    "JUDGE_ERROR excluded from the denominator"),
        "excluded": {"by_rule": sorted(EXCLUDED),
                     "no_legible_verdict": excluded_no_verdict,
                     "one_side_only": only_before + only_after},
        "n_questions": n,
        "judge_errors": judge_errors,
        "correctness": {"uncorrected": mean_before, "corrected": mean_after},
        "paired_difference": mean_diff,
        "bootstrap_95": [lo, hi],
        "resamples": RESAMPLES,
        "seed": SEED,
        "sign_test": {"up": len(up), "down": len(down),
                      "unchanged": n - len(moved)},
        "questions_changed": moved,
        "per_question": rows,
    }
    args.out = Path(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nSaved to {args.out.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
