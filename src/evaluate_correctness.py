#!/usr/bin/env python3
"""
Measure whether the answer is right, not merely whether one was produced.

    python src/evaluate_correctness.py
    python src/evaluate_correctness.py --provider echo    # free dry run

THE GAP THIS FILLS

The harness measured four things and none of them was correctness:

    retrieval     did the evidence arrive
    refusal       did it answer or decline
    citation      does every figure carry a source that was actually supplied
    groundedness  is each claim present in the excerpt it cites

A claim can be perfectly grounded and still answer a different question. Q035 asks
which of two companies reports higher revenue; the labeled figure for Deckers is
$5,378,411 thousand and the system answered $5,472,296 thousand. Both numbers
appear in the filing, the citation was valid, groundedness passed -- and the answer
is wrong. Nothing in the harness noticed.

So this compares the generated answer against the labeled one, which exists
because someone read the filings.

    CORRECT             states the labeled fact
    PARTIALLY_CORRECT   states some of it, or states it without a part the
                        question asked for
    INCORRECT           states something different
    REFUSED             declined; scored separately, not as a failure

Judging is asymmetric on purpose: the labeled answer is the reference and the
generated answer is what is being checked. The judge is told to ignore wording,
ordering and units expressed differently, and to care only about the facts.

THE SECOND THING THIS DETECTS

Four questions were answered correctly while none of their gold chunks were
retrieved. Two explanations, and they call for opposite responses:

    the labels are incomplete -- other chunks carry the same fact, unlabeled
    the model answered from prior knowledge -- which the prompt forbids

"HOKA, UGG and Teva" is public knowledge. A model that produces it without reading
it has bypassed retrieval entirely, and the citation check cannot see that: the
citation is valid, the excerpt exists, and the claim happens to be true. Every
such case is flagged here for reading, because only reading the cited excerpt
distinguishes the two.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("correctness")

JUDGE_SYSTEM = """You compare a generated answer against a reference answer and
report whether the generated one is factually correct.

The reference was written by a person who read the source document. Treat it as
correct. Your task is only to say whether the generated answer states the same
facts.

Ignore differences in wording, sentence order, formatting, and citation markers.
Ignore units expressed differently for the same quantity: "$7.5 billion" and
"$7,489 million" are the same figure. Ignore extra detail the generated answer
adds, provided it does not contradict the reference.

Verdicts:

CORRECT             every fact the reference states is present and none is
                    contradicted
PARTIALLY_CORRECT   some facts the reference states are present, others are
                    missing, and none is contradicted
INCORRECT           a fact contradicts the reference -- a different figure, a
                    different company, a different fiscal year

A different number for the same quantity is INCORRECT, not PARTIALLY_CORRECT. A
missing number is PARTIALLY_CORRECT.

Reply with JSON and nothing else:

{"verdict": "CORRECT", "reason": "one short sentence"}"""

JUDGE_MAX_TOKENS = 512
VERDICTS = ("CORRECT", "PARTIALLY_CORRECT", "INCORRECT")


def judge_answer(provider, question: str, reference: str, generated: str
                 ) -> tuple[str, str, str]:
    """Returns (verdict, reason, raw reply)."""
    reply = provider.complete(
        system=JUDGE_SYSTEM,
        user=(f"QUESTION:\n{question}\n\n"
              f"REFERENCE ANSWER:\n{reference}\n\n"
              f"GENERATED ANSWER:\n{generated}"),
        max_tokens=JUDGE_MAX_TOKENS,
    ).strip()

    if not reply:
        return "JUDGE_ERROR", "", "(empty reply)"

    import re
    m = re.search(r'"verdict"\s*:\s*"([A-Z_]+)"', reply)
    reason = ""
    rm = re.search(r'"reason"\s*:\s*"([^"]*)"', reply)
    if rm:
        reason = rm.group(1)

    if m and m.group(1) in VERDICTS:
        return m.group(1), reason, reply

    upper = reply.upper()
    # PARTIALLY_CORRECT contains CORRECT, so order matters.
    for v in ("PARTIALLY_CORRECT", "INCORRECT", "CORRECT"):
        if v in upper:
            return v, reason, reply
    return "JUDGE_ERROR", reason, reply


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure answer correctness")
    ap.add_argument("--generation", default="eval/results/generation.json", type=Path)
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("--out", default="eval/results/correctness.json", type=Path)
    ap.add_argument("--provider")
    ap.add_argument("--run", type=int, default=0,
                    help="which run of each question to judge")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "httpcore", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if not args.generation.exists():
        log.error("%s not found — run src/evaluate_generation.py first",
                  args.generation)
        return 2

    import yaml
    from llm import get_provider

    provider = get_provider(args.provider)
    data = json.loads(args.generation.read_text(encoding="utf-8"))
    questions = {q["id"]: q for q in
                 yaml.safe_load(args.questions.read_text(encoding="utf-8"))}

    # One run per question. Correctness is a property of the answer, and judging
    # three near-identical answers triples the cost for very little.
    rows = [r for r in data["records"]
            if r["answerable"] and r["run"] == args.run]

    log.info("%d answerable questions, run %d, judge %s\n",
             len(rows), args.run, provider.name)

    results, verdicts = [], defaultdict(int)
    started = time.time()

    for r in rows:
        q = questions.get(r["id"], {})
        reference = q.get("gold_answer") or ""
        gold = set(r["gold_chunk_ids"])
        retrieved = set(r["excerpt_ids"])
        gold_found = sorted(gold & retrieved)

        if r["refused"]:
            verdict, reason, raw = "REFUSED", "declined to answer", ""
        elif not reference:
            verdict, reason, raw = "NO_REFERENCE", "no labeled answer", ""
        else:
            verdict, reason, raw = judge_answer(
                provider, q.get("question", ""), reference, r["text"])

        verdicts[verdict] += 1

        # Correct without any labeled evidence retrieved. Either the labels are
        # incomplete or the model did not need the excerpts, and those demand
        # opposite fixes.
        unsourced = verdict in ("CORRECT", "PARTIALLY_CORRECT") and not gold_found

        results.append({
            "id": r["id"], "type": r["type"], "verdict": verdict,
            "reason": reason, "raw": raw,
            "reference": reference, "generated": r["text"],
            "gold_chunk_ids": sorted(gold), "gold_retrieved": gold_found,
            "cited": r["cited"],
            "cited_chunk_ids": [r["excerpt_ids"][c - 1] for c in r["cited"]
                                if 1 <= c <= len(r["excerpt_ids"])],
            "correct_without_gold": unsourced,
        })

        flag = "  <-- correct, no gold chunk retrieved" if unsourced else ""
        log.info("  %-6s %-26s %s%s", r["id"], r["type"][:25], verdict, flag)

    decided = sum(verdicts[v] for v in VERDICTS)
    n = len(rows)

    print(f"\n{'=' * 66}")
    print(f"{n} answerable questions  ·  {time.time() - started:.0f}s")
    print("=" * 66)

    print(f"\n{'verdict':<24}{'n':>5}{'of all':>10}{'of answered':>14}")
    print("-" * 55)
    for v in VERDICTS:
        k = verdicts[v]
        print(f"{v:<24}{k:>5}{k / n:>10.1%}"
              f"{(k / decided if decided else 0):>14.1%}")
    print("-" * 55)
    for v in ("REFUSED", "NO_REFERENCE", "JUDGE_ERROR"):
        if verdicts[v]:
            print(f"{v:<24}{verdicts[v]:>5}{verdicts[v] / n:>10.1%}")

    print(f"\n  answered correctly       {verdicts['CORRECT'] / n:>7.1%}  of all "
          f"answerable questions")
    print(f"  answered incorrectly     {verdicts['INCORRECT'] / n:>7.1%}  <-- the "
          f"figure the harness could not see before")

    by_type = defaultdict(lambda: defaultdict(int))
    for row in results:
        by_type[row["type"]][row["verdict"]] += 1
    print(f"\n{'type':<20}{'n':>4}" + "".join(f"{v[:9]:>11}" for v in VERDICTS)
          + f"{'REFUSED':>11}")
    print("-" * 68)
    for t in sorted(by_type):
        c = by_type[t]
        total = sum(c.values())
        print(f"{t:<20}{total:>4}"
              + "".join(f"{c[v]:>11}" for v in VERDICTS)
              + f"{c['REFUSED']:>11}")

    unsourced = [r for r in results if r["correct_without_gold"]]
    if unsourced:
        print(f"\n{'=' * 66}")
        print(f"{len(unsourced)} answers correct with no labeled chunk retrieved")
        print("=" * 66)
        print("Either the labels are incomplete, or the model answered without")
        print("needing the excerpts. Read the cited chunk to tell which:\n")
        for r in unsourced:
            print(f"  {r['id']:<7} cited chunks {r['cited_chunk_ids']}, "
                  f"labeled {r['gold_chunk_ids']}")
            print(f"          python src/find_gold.py x --chunk "
                  f"{r['cited_chunk_ids'][0] if r['cited_chunk_ids'] else '?'}")

    wrong = [r for r in results if r["verdict"] == "INCORRECT"]
    if wrong:
        print(f"\n{'=' * 66}\n{len(wrong)} INCORRECT\n{'=' * 66}")
        for r in wrong:
            print(f"\n  {r['id']}  {r['reason']}")
            print(f"    labeled:   {r['reference'][:110]}")
            print(f"    generated: {' '.join(r['generated'].split())[:110]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": datetime.now().isoformat(timespec="seconds"),
        "judge": os.environ.get("GENERATION_MODEL", provider.name),
        "run_judged": args.run,
        "n_answerable": n,
        "counts": dict(verdicts),
        "correct_rate": verdicts["CORRECT"] / n if n else 0,
        "incorrect_rate": verdicts["INCORRECT"] / n if n else 0,
        "note": (
            "Correctness compares the generated answer against a reference "
            "written by reading the filing. It is not groundedness: an answer can "
            "be fully supported by the excerpt it cites and still state a "
            "different fact than the question asked for."
        ),
        "results": results,
    }, indent=1), encoding="utf-8")
    print(f"\nSaved to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
