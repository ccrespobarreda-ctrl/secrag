#!/usr/bin/env python3
"""
Does better ordering produce better answers? The paired analysis, as specified.

    python analyse_ordering.py

WHAT THIS IS

docs/decision-rule-ordering.md was written and committed before the run it
decides. It specifies three things this script does not get to reconsider:

  1. Correctness against the labelled answer decides it, not groundedness.
     Groundedness is conditional on the excerpts that arrived, so it rewards
     whichever branch risks least.
  2. The analysis is PAIRED -- the same questions in both branches, differences
     per question, every question that changes verdict named. Two aggregate
     rates over 48 questions have little power.
  3. If the paired difference's interval spans zero, that is the result, and it
     is not read as support for whichever number happens to be higher.

Aggregate counts over these files show hybrid ahead by about four points. That
is the comparison the rule declines in advance, which is why it exists.

HOW VERDICTS ARE SCORED, DECLARED BEFORE THE NUMBERS

  CORRECT             1
  PARTIALLY_CORRECT   0   the rule says correctness against the labelled
                          answer; partial is not correct
  INCORRECT           0
  REFUSED             0   on an answerable question this is a false refusal,
                          and it is also a guardrail signal
  JUDGE_ERROR         excluded, not scored zero. Counting a failed judge call
                          as a wrong answer is the defect recorded in
                          measurement-honesty.md under an empty completion.

WHAT THIS CANNOT DECIDE

The rule gives groundedness, refusal on unanswerable questions and false refusal
a veto: a branch that raises false refusal or lowers refusal on unanswerable
questions does not win on correctness alone. Those live in the generation result
files, not here. This script reports the correctness verdict and prints what
still has to be read before it counts.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "eval" / "results"
BRANCHES = {"hybrid": "corr_hybrid_r{}.json", "keyword": "corr_keyword_r{}.json"}
RUNS = (0, 1, 2)
SCORE = {"CORRECT": 1.0, "PARTIALLY_CORRECT": 0.0, "INCORRECT": 0.0,
         "REFUSED": 0.0}
ID_KEYS = ("id", "question_id", "qid", "question")
VERDICT_KEYS = ("verdict", "judge", "judgement", "judgment", "result")


def records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    for key in ("results", "records", "questions", "answers", "items"):
        if isinstance(data.get(key), list):
            return data[key]
    raise SystemExit(f"{path.name}: cannot find the record list. Top-level keys: "
                     f"{sorted(data)}")


def pick(row: dict, candidates: tuple[str, ...], what: str) -> str:
    for key in candidates:
        if key in row and isinstance(row[key], str):
            return key
    raise SystemExit(f"cannot find the {what} field. Keys present: {sorted(row)}")


def load() -> tuple[dict[str, dict[str, list[float]]], dict[str, int], list[str]]:
    scores: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"hybrid": [], "keyword": []})
    excluded: dict[str, int] = defaultdict(int)
    unknown: set[str] = set()
    id_key = verdict_key = None

    for branch, pattern in BRANCHES.items():
        for run in RUNS:
            path = RESULTS / pattern.format(run)
            if not path.is_file():
                raise SystemExit(f"{path} not found")
            rows = records(path)
            if id_key is None:
                id_key = pick(rows[0], ID_KEYS, "question id")
                verdict_key = pick(rows[0], VERDICT_KEYS, "verdict")
                print(f"reading `{id_key}` and `{verdict_key}` from "
                      f"{len(rows)} records per file\n")
            for row in rows:
                verdict = str(row[verdict_key]).upper()
                qid = str(row[id_key])
                if verdict == "JUDGE_ERROR":
                    excluded[branch] += 1
                    continue
                if verdict not in SCORE:
                    unknown.add(verdict)
                    continue
                scores[qid][branch].append(SCORE[verdict])

    return scores, excluded, sorted(unknown)


def bootstrap(diffs: list[float], reps: int = 20000) -> tuple[float, float]:
    rng = random.Random(20260908)
    n = len(diffs)
    means = sorted(statistics.fmean(rng.choices(diffs, k=n)) for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


def main() -> int:
    scores, excluded, unknown = load()
    if unknown:
        print(f"unrecognised verdicts, not scored: {unknown}\n")

    paired = {q: v for q, v in scores.items() if v["hybrid"] and v["keyword"]}
    dropped = sorted(set(scores) - set(paired))

    diffs, moved = [], []
    for qid, v in sorted(paired.items()):
        h, k = statistics.fmean(v["hybrid"]), statistics.fmean(v["keyword"])
        diffs.append(h - k)
        if h != k:
            moved.append((qid, h, k))

    print(f"{len(paired)} questions answered by both branches"
          + (f", {len(dropped)} dropped for want of a pair: {dropped}"
             if dropped else ""))
    for branch, n in sorted(excluded.items()):
        print(f"{n} judge error(s) excluded from {branch}")

    mean = statistics.fmean(diffs)
    lo, hi = bootstrap(diffs)
    print(f"\nHybrid correctness   {statistics.fmean(statistics.fmean(v['hybrid']) for v in paired.values()):.3f}")
    print(f"Keyword correctness  {statistics.fmean(statistics.fmean(v['keyword']) for v in paired.values()):.3f}")
    print(f"\nPAIRED DIFFERENCE    {mean:+.3f}   95% CI [{lo:+.3f}, {hi:+.3f}]")
    print("  (hybrid minus keyword, per question, averaged over runs;"
          f" {len(diffs)} pairs,\n   20,000 bootstrap resamples over questions)")

    print(f"\n{len(moved)} question(s) where the branches disagree:")
    for qid, h, k in moved:
        print(f"  {qid:<8} hybrid {h:.2f}   keyword {k:.2f}"
              f"   {'hybrid' if h > k else 'keyword'}")

    print()
    if lo <= 0.0 <= hi:
        print("THE INTERVAL SPANS ZERO.")
        print(
            "Under the rule written before this run, that is the result: the two\n"
            "are indistinguishable at this sample size, and it is not read as\n"
            "support for whichever number is higher. The rule also names what\n"
            "comes next -- the judge's 97.2% self-agreement is the binding\n"
            "constraint, so an independent judge over a sample is the next\n"
            "measurement, not a rerun of this one."
        )
    elif mean > 0:
        print("HYBRID LEADS, INTERVAL CLEAR OF ZERO.")
        print(
            "Ordering does produce better answers. Under the rule this justifies\n"
            "the dense half on evidence rather than convention, and the README\n"
            "should say which questions it wins and why -- they are named above."
        )
    else:
        print("KEYWORD MATCHES OR BEATS HYBRID, INTERVAL CLEAR OF ZERO.")
        print(
            "Under the rule, ordering does not buy answers either, and the README\n"
            "describes a lexical system with a dense component that was measured\n"
            "and dropped."
        )

    print(
        "\nNOT DECIDED HERE. The rule gives false refusal, refusal on\n"
        "unanswerable questions and groundedness a veto over the correctness\n"
        "verdict. Those are in the generation result files for the same two\n"
        "branches, and they must be read before this is written up: a branch\n"
        "that raises false refusal does not win on correctness alone."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.stderr.close()
        raise SystemExit(1)
