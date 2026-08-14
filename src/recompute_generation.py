#!/usr/bin/env python3
"""
Recompute the generation metrics from saved responses, with no API calls.

    python src/recompute_generation.py

Three of the numbers in the last run were wrong, and all three were the harness
misjudging correct behaviour rather than the system misbehaving:

  A hallucination that was not one. The Yeti question was refused in prose --
  "an exact number cannot be determined from these excerpts", including an
  explicit rejection of the twelve-countries-of-employees trap -- and scored as
  answering, because the check looked only for the exact marker. It inflated the
  one metric that has to be zero.

  Nine citation failures that were not failures. Markdown bullets and long
  sentences carrying several figures were split away from the citation at their
  end, so a cited claim was reported as uncited.

The responses are unchanged; only the judgement of them was wrong. Rerunning the
model would have cost money and told us nothing new, so this rereads what is on
disk.
"""
from __future__ import annotations
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate as G  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Recompute metrics from saved responses")
    ap.add_argument("--results", default="eval/results/generation.json", type=Path)
    ap.add_argument("--out", type=Path, help="write the corrected file")
    args = ap.parse_args()

    if not args.results.exists():
        print(f"{args.results} not found")
        return 2

    data = json.loads(args.results.read_text(encoding="utf-8"))
    before = {
        "refusal": data["refusal_rate"],
        "false_refusal": data["false_refusal_rate"],
        "hallucination": data["hallucination_rate"],
        "citation_problems": sum(1 for r in data["records"] if r["problems"]),
    }

    # The original verdict is read before anything is overwritten. An earlier
    # version compared against the field it had already replaced and printed
    # "refused -> refused", which says nothing.
    original = {(r["id"], r["run"]): (r["refused"], bool(r["problems"]))
                for r in data["records"]}

    changed_refusal, changed_problems = [], []
    for r in data["records"]:
        was_refused = original[(r["id"], r["run"])][0]
        now_refused = G.is_refusal(r["text"])
        if was_refused != now_refused:
            changed_refusal.append((r["id"], r["run"], was_refused, now_refused))
        r["refused"] = now_refused

        _, problems = G.verify_citations(r["text"], len(r["excerpt_ids"]))
        if bool(r["problems"]) != bool(problems):
            changed_problems.append((r["id"], r["run"],
                                     len(r["problems"]), len(problems)))
        r["problems"] = problems

    recs = data["records"]
    ans = [r for r in recs if r["answerable"]]
    una = [r for r in recs if not r["answerable"]]

    def rate(rows, pred):
        return sum(1 for r in rows if pred(r)) / len(rows) if rows else 0.0

    after = {
        "refusal": rate(una, lambda r: r["refused"]),
        "false_refusal": rate(ans, lambda r: r["refused"]),
        "hallucination": rate(una, lambda r: not r["refused"]),
        "citation_problems": sum(1 for r in recs if r["problems"]),
    }

    print(f"{len(recs)} saved responses, rejudged. No API calls.\n")
    print(f"{'metric':<26}{'before':>10}{'after':>10}")
    print("-" * 46)
    for k in ("refusal", "false_refusal", "hallucination"):
        print(f"{k.replace('_', ' '):<26}{before[k]:>9.1%}{after[k]:>10.1%}")
    print(f"{'citation problems':<26}{before['citation_problems']:>10}"
          f"{after['citation_problems']:>10}")

    if changed_refusal:
        print(f"\n{len(changed_refusal)} responses changed their refusal verdict:")
        for qid, run, was, now in changed_refusal[:8]:
            print(f"    {qid} run {run}: {'answered' if was else 'refused'}"
                  f" -> {'refused' if now else 'answered'}")

    if changed_problems:
        print(f"\n{len(changed_problems)} responses changed their citation verdict:")
        for qid, run, n_was, n_now in changed_problems[:10]:
            print(f"    {qid} run {run}: {n_was} problem(s) -> {n_now}")

    by_type = defaultdict(list)
    for r in recs:
        by_type[r["type"]].append(r)
    print(f"\n{'type':<28}{'n':>5}{'refused':>10}{'answered':>10}")
    print("-" * 53)
    for t in sorted(by_type):
        rows = by_type[t]
        print(f"{t:<28}{len(rows):>5}"
              f"{rate(rows, lambda r: r['refused']):>10.1%}"
              f"{rate(rows, lambda r: not r['refused']):>10.1%}")

    data.update(refusal_rate=after["refusal"],
                false_refusal_rate=after["false_refusal"],
                hallucination_rate=after["hallucination"],
                rejudged=True)

    out = args.out or args.results
    out.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"\nWritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
