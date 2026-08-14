#!/usr/bin/env python3
"""
Read the generation results and show what needs a human eye.

    python src/review_generation.py
    python src/review_generation.py --show false-refusal
    python src/review_generation.py --question Q015
    python src/review_generation.py --compare-gold

Aggregate rates say the system refuses 52% of answerable questions. They do not
say which ones, or why, and that is where the next fix comes from. This prints the
cases behind each number.

WHAT ONLY A PERSON CAN CHECK

--compare-gold puts each generated answer beside the labeled answer. An automatic
judge can say a claim is supported by the excerpt it cites; it cannot say the
answer is the one the question asked for. The gold answers exist because someone
read the filings, and comparing against them is the only check that closes the
loop.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402


def wrap(text: str, width: int = 88, indent: str = "      ") -> str:
    import textwrap
    body = " ".join(text.split())
    return "\n".join(indent + line for line in textwrap.wrap(body, width))


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"{path} not found. Run src/evaluate_generation.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def summarise(data: dict) -> None:
    recs = data["records"]
    by_q = defaultdict(list)
    for r in recs:
        by_q[r["id"]].append(r)

    print(f"model {data['model']}  ·  {data['runs']} runs  ·  "
          f"top_k {data.get('top_k', '?')}  ·  {data['generated']}")
    print(f"refusal {data['refusal_rate']:.1%}  ·  "
          f"false refusal {data['false_refusal_rate']:.1%}  ·  "
          f"hallucination {data['hallucination_rate']:.1%}\n")

    # Questions grouped by how consistently they behaved. A question that refuses
    # every run is a different problem from one that flips: the first is a
    # retrieval gap, the second is sampling variance.
    always_refused, sometimes, always_answered = [], [], []
    for qid, runs in by_q.items():
        refusals = sum(r["refused"] for r in runs)
        row = (qid, runs[0]["type"], runs[0]["answerable"], refusals, len(runs))
        if refusals == len(runs):
            always_refused.append(row)
        elif refusals == 0:
            always_answered.append(row)
        else:
            sometimes.append(row)

    print(f"{'behaviour':<34}{'n':>5}")
    print("-" * 40)
    print(f"{'refused in every run':<34}{len(always_refused):>5}")
    print(f"{'refused in some runs':<34}{len(sometimes):>5}")
    print(f"{'answered in every run':<34}{len(always_answered):>5}")

    fr_always = [r for r in always_refused if r[2]]
    fr_some = [r for r in sometimes if r[2]]

    print(f"\n{len(fr_always)} answerable questions were refused in EVERY run")
    print("  These are retrieval failures, not model caution: the excerpts did")
    print("  not contain the answer, so refusing was correct.")
    if fr_always:
        for qid, qtype, _, n, total in sorted(fr_always):
            print(f"    {qid}  {qtype}")

    print(f"\n{len(fr_some)} answerable questions refused in SOME runs")
    print("  Same excerpts, different decision. This is sampling variance, and it")
    print("  is the cost of models no longer accepting temperature=0.")
    if fr_some:
        for qid, qtype, _, n, total in sorted(fr_some):
            print(f"    {qid}  {qtype:<14} refused {n}/{total}")


def show_cases(data: dict, which: str, limit: int) -> None:
    recs = data["records"]

    if which == "false-refusal":
        rows = [r for r in recs if r["answerable"] and r["refused"]]
        title = "REFUSED A QUESTION IT COULD ANSWER"
    elif which == "hallucination":
        rows = [r for r in recs if not r["answerable"] and not r["refused"]]
        title = "ANSWERED A QUESTION IT COULD NOT ANSWER"
    elif which == "citation-problem":
        rows = [r for r in recs if r["problems"]]
        title = "FAILED CITATION VERIFICATION"
    elif which == "answered":
        rows = [r for r in recs if r["answerable"] and not r["refused"]]
        title = "ANSWERED"
    elif which == "judge-raw":
        # What the judge actually said when its verdict could not be read. A
        # groundedness rate computed over parsed answers only is not a rate.
        print(f"\n{'=' * 92}\nJUDGE FAILURES -- no verdict could be read\n{'=' * 92}")
        n = 0
        for r in recs:
            for j in r.get("judged", []):
                if j["verdict"] not in ("unparsed", "judge_error"):
                    continue
                n += 1
                if n > limit:
                    continue
                fuentes = ", ".join(j.get("sources", [])) or j.get("source", "?")
                print(f"\n  {r['id']} run {r['run']}  cites {j['cited']}  {fuentes}")
                print(f"    JUDGE SAID: {j.get('raw', '(not recorded)')!r}")
                print(f"    ON CLAIM:")
                print(wrap(j["claim"], indent="      "))
        if n == 0:
            print("\n  None. Either every verdict parsed, or the results predate")
            print("  raw replies being saved -- re-run the evaluation to capture them.")
        else:
            print(f"\n  {n} unparsed verdicts.")
        return

    elif which == "unsupported":
        # Claims the judge could not find in the excerpt they cite. These are the
        # cases where citation verification passed -- the excerpt exists and was
        # sent -- and the claim still is not in it.
        print(f"\n{'=' * 92}\nCLAIMS THE JUDGE FOUND UNSUPPORTED\n{'=' * 92}")
        n = 0
        for r in recs:
            for j in r.get("judged", []):
                if j["verdict"] != "unsupported":
                    continue
                n += 1
                if n > limit:
                    continue
                ids = j.get("chunk_ids") or [j.get("chunk_id")]
                fuentes = ", ".join(j.get("sources", [])) or j.get("source", "?")
                print(f"\n  {r['id']} run {r['run']}  cites {j['cited']} -> "
                      f"chunks {ids}  {fuentes}")
                print(f"    CLAIM:")
                print(wrap(j["claim"], indent="      "))
        print(f"\n  {n} unsupported claims in total.")
        print("  Read the cited chunk with: python src/find_gold.py x --chunk N")
        return
    else:
        raise SystemExit(f"unknown case type {which!r}")

    print(f"\n{'=' * 92}\n{title}  ({len(rows)} responses)\n{'=' * 92}")
    for r in rows[:limit]:
        print(f"\n  {r['id']}  run {r['run']}  {r['type']}")
        print(wrap(r["text"]))
        if r["problems"]:
            for p in r["problems"]:
                print(f"      PROBLEM: {p}")
        if r["gold_chunk_ids"]:
            hit = set(r["cited"]) and any(
                r["excerpt_ids"][c - 1] in r["gold_chunk_ids"]
                for c in r["cited"] if 1 <= c <= len(r["excerpt_ids"]))
            gold_in = [g for g in r["gold_chunk_ids"] if g in r["excerpt_ids"]]
            print(f"      gold chunks retrieved: {gold_in or 'none'}"
                  f"   cited a gold chunk: {bool(hit)}")

    if len(rows) > limit:
        print(f"\n  ... {len(rows) - limit} more. Use --limit to see them.")


def compare_gold(data: dict, questions_path: Path, limit: int) -> None:
    import yaml
    questions = {q["id"]: q for q in
                 yaml.safe_load(questions_path.read_text(encoding="utf-8"))}

    answered = [r for r in data["records"]
                if r["answerable"] and not r["refused"]]
    seen, rows = set(), []
    for r in answered:
        if r["id"] not in seen:
            seen.add(r["id"])
            rows.append(r)

    print(f"\n{'=' * 92}")
    print("GENERATED ANSWER vs LABELED ANSWER")
    print("An automatic judge checks whether a claim matches its excerpt. Only a")
    print("person can check whether the answer is the one the question asked for.")
    print("=" * 92)

    for r in rows[:limit]:
        q = questions.get(r["id"], {})
        print(f"\n  {r['id']}  {r['type']}")
        print(f"    Q: {q.get('question', '?')}")
        print(f"\n    LABELED:")
        print(wrap(str(q.get("gold_answer") or ""), indent="      "))
        print(f"\n    GENERATED:")
        print(wrap(r["text"], indent="      "))
        print(f"\n    {'-' * 84}")

    if len(rows) > limit:
        print(f"\n  ... {len(rows) - limit} more questions answered.")
    print("\n  For each: does the generated answer state the same fact? If it")
    print("  states a different figure, or the right figure for the wrong company,")
    print("  the citation check and the judge would both have passed it.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Review generation results")
    ap.add_argument("--results", default="eval/results/generation.json", type=Path)
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("--show", choices=["false-refusal", "hallucination",
                                       "citation-problem", "answered",
                                       "unsupported", "judge-raw"])
    ap.add_argument("--question", help="print every run of one question")
    ap.add_argument("--compare-gold", action="store_true")
    ap.add_argument("--limit", type=int, default=6)
    args = ap.parse_args()

    data = load(args.results)

    if args.question:
        rows = [r for r in data["records"] if r["id"] == args.question.upper()]
        if not rows:
            print(f"No records for {args.question}")
            return 1
        print(f"{args.question.upper()}  ·  {rows[0]['type']}  ·  "
              f"answerable={rows[0]['answerable']}")
        print(f"excerpts retrieved: {rows[0]['excerpt_ids']}")
        print(f"gold chunks:        {rows[0]['gold_chunk_ids'] or 'none'}")
        overlap = set(rows[0]["excerpt_ids"]) & set(rows[0]["gold_chunk_ids"])
        print(f"gold retrieved:     {sorted(overlap) or 'NONE — retrieval failed'}")
        for r in rows:
            print(f"\n  run {r['run']}  {'refused' if r['refused'] else 'answered'}"
                  f"  cited {r['cited'] or '-'}")
            print(wrap(r["text"]))
            for p in r["problems"]:
                print(f"      PROBLEM: {p}")
        return 0

    summarise(data)

    if args.show:
        show_cases(data, args.show, args.limit)
    if args.compare_gold:
        compare_gold(data, args.questions, args.limit)

    if not args.show and not args.compare_gold:
        print("\n  --show false-refusal      the questions it would not answer")
        print("  --show citation-problem   answers that failed verification")
        print("  --compare-gold            generated answers beside the labels")
        print("  --question Q015           every run of one question")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
