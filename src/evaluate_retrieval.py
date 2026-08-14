#!/usr/bin/env python3
"""
Measure retrieval. No language model involved.

    python src/evaluate_retrieval.py
    python src/evaluate_retrieval.py --sweep
    python src/evaluate_retrieval.py --sabotage

Retrieval quality bounds generation quality: if the correct chunk is not in the
top k, no model can answer from it. Measuring retrieval on its own turns a wrong
answer from a question with two suspects into one with a number.

WHAT IS MEASURED

  Recall@k   Did any gold chunk appear in the top k? The ceiling on answerable
             questions.
  MRR        1 / rank of the first gold chunk, 0 if absent. Rewards putting it
             first rather than eighth, which Recall@k cannot see.

Unanswerable questions carry no gold chunks and are excluded here. What they
measure — whether the system refuses — belongs to the generation harness. Their
retrieval behaviour is still worth a glance, so the count of chunks returned for
them is reported separately: a question with no answer should ideally not pull
back confident-looking passages.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("eval")


def load_questions(path: Path, cur) -> list[dict]:
    """
    Read the questions and resolve their labels against the corpus.

    Resolution is not a formality. A label that no longer holds is not an
    unlabeled question, it is a broken measurement, and the difference matters:
    an unlabeled question is skipped and said so, while a broken one would be
    scored against text that is not the answer.
    """
    import labels as L

    questions = L.load(path)
    problems = L.resolve(cur, questions)

    if problems:
        log.error("%d gold label(s) no longer hold:", len(problems))
        for p in problems[:8]:
            log.error("  %-7s %s  %s", p["id"], p["kind"], p["detail"])
        if len(problems) > 8:
            log.error("  ... %d more", len(problems) - 8)
        log.error("Run src/verify_labels.py. Every number below is measured "
                  "against these labels.")

    unlabeled = [q["id"] for q in questions
                 if q.get("answerable") and not q.get("gold_chunk_ids")]
    if unlabeled:
        log.warning("%d answerable questions have no usable label and are "
                    "skipped: %s", len(unlabeled), ", ".join(unlabeled[:8]))
        log.warning("Label them with src/find_gold.py before trusting any number "
                    "below.")
    return questions


def score_one(hits, gold: set[int], k: int) -> tuple[float, float, float]:
    """
    Recall@k, reciprocal rank, and coverage for a single question.

    Coverage exists because Recall@k lies on multi-chunk questions. Levi's
    segment question needs three chunks: one naming the segments and two holding
    the performance tables. One of the three arrived, so Recall@8 scored it a
    perfect hit -- while a model given those excerpts could name the segments and
    would have no idea how any of them performed.

    Coverage is the fraction of gold chunks retrieved. For single-chunk questions
    it equals Recall@k; the two only diverge where the answer is distributed, and
    that divergence is the finding.
    """
    ids = [h.chunk_id for h in hits[:k]]
    found = [i for i in ids if i in gold]
    hit = 1.0 if found else 0.0

    rr = 0.0
    for rank, chunk_id in enumerate(ids, 1):
        if chunk_id in gold:
            rr = 1.0 / rank
            break

    coverage = len(set(found)) / len(gold) if gold else 0.0
    return hit, rr, coverage


def evaluate(cur, questions, embed, strategies, k: int) -> dict:
    answerable = [q for q in questions
                  if q.get("answerable") and q.get("gold_chunk_ids")]
    unanswerable = [q for q in questions if not q.get("answerable")]

    results = {name: {"recall": [], "mrr": [], "coverage": [], "by_type": {},
                      "cov_by_type": {}}
               for name in strategies}

    for q in answerable:
        gold = set(q["gold_chunk_ids"])
        qv = embed(q["question"])
        for name, fn in strategies.items():
            hits = fn(cur, q["question"], qv)
            recall, rr, cov = score_one(hits, gold, k)
            results[name]["recall"].append(recall)
            results[name]["mrr"].append(rr)
            results[name]["coverage"].append(cov)
            results[name]["by_type"].setdefault(q["type"], []).append(recall)
            results[name]["cov_by_type"].setdefault(q["type"], []).append(cov)

    for name in strategies:
        r = results[name]
        n = len(r["recall"]) or 1
        r["recall_at_k"] = sum(r["recall"]) / n
        r["mean_rr"] = sum(r["mrr"]) / n
        r["coverage"] = sum(r["coverage"]) / n
        r["n"] = len(r["recall"])

    results["_unanswerable"] = len(unanswerable)
    results["_answerable"] = len(answerable)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure retrieval quality")
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("-k", type=int, default=C.RETRIEVAL_TOP_K)
    ap.add_argument("--sweep", action="store_true",
                    help="try several fusion constants")
    ap.add_argument("--sabotage", action="store_true",
                    help="run the degraded retrievers and confirm the metrics move")
    ap.add_argument("--save", type=Path, help="write results as JSON")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    from search import embed_query

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    questions = load_questions(args.questions, cur)

    strategies = {
        "semantic": lambda c, q, v: R.search_semantic(c, v, top_k=args.k),
        "keyword":  lambda c, q, v: R.search_keyword(c, q, top_k=args.k),
        "hybrid":   lambda c, q, v: R.search_hybrid(c, q, v, top_k=args.k),
        # What the system actually does: hybrid plus the company constraint.
        "hybrid+company": lambda c, q, v: R.search(c, q, v, top_k=args.k),
    }

    if args.sabotage:
        # Each degradation disables one capability. A degradation that moves no
        # metric means the harness cannot see that failure, and that is a finding
        # about the harness rather than a pass.
        strategies.update({
            # Every degradation takes (cur, query, query_vector) so the harness
            # can call them uniformly, even when a given path ignores one of the
            # two. An earlier version passed them positionally in the order each
            # function happened to want, and the signatures drifted apart.
            "SABOTAGE starved":    lambda c, q, v: R.degraded_starved(c, q, v),
            "SABOTAGE no-keyword": lambda c, q, v: R.degraded_semantic_only(c, q, v, top_k=args.k),
            "SABOTAGE no-semantic": lambda c, q, v: R.degraded_keyword_only(c, q, v, top_k=args.k),
            "SABOTAGE or-keyword": lambda c, q, v: R.degraded_or_keyword(c, q, v, top_k=args.k),
            "SABOTAGE no-company": lambda c, q, v: R.degraded_no_company_filter(c, q, v, top_k=args.k),
        })

    results = evaluate(cur, questions, embed_query, strategies, args.k)

    print(f"\n{results['_answerable']} answerable questions with labels, "
          f"{results['_unanswerable']} unanswerable")
    if not results["_answerable"]:
        print("\nNothing to measure. Label questions with src/find_gold.py first.")
        conn.close()
        return 1

    print(f"\n{'strategy':<22}{'Recall@' + str(args.k):>12}{'MRR':>10}"
          f"{'Coverage':>11}")
    print("-" * 55)
    baseline = results.get("hybrid+company", {}).get("recall_at_k", 0)
    for name in strategies:
        r = results[name]
        delta = ""
        if name.startswith("SABOTAGE"):
            drop = r["recall_at_k"] - baseline
            delta = f"   {drop:+.3f} vs hybrid+company"
            if abs(drop) < 0.01:
                delta += "   <-- moved nothing"
        print(f"{name:<22}{r['recall_at_k']:>12.3f}{r['mean_rr']:>10.3f}"
              f"{r['coverage']:>11.3f}{delta}")

    # Per question type: an aggregate can hide a strategy that is excellent on
    # one kind of question and useless on another.
    types = sorted({t for name in strategies for t in results[name]["by_type"]})
    if types:
        print(f"\nCoverage by question type -- the fraction of gold chunks "
              f"retrieved")
        print(f"{'strategy':<22}" + "".join(f"{t[:14]:>16}" for t in types))
        print("-" * (22 + 16 * len(types)))
        for name in strategies:
            row = f"{name:<22}"
            for t in types:
                vals = results[name]["cov_by_type"].get(t, [])
                row += f"{(sum(vals) / len(vals) if vals else 0):>16.3f}"
            print(row)

        print(f"\nRecall@{args.k} by question type")
        print(f"{'strategy':<22}" + "".join(f"{t[:14]:>16}" for t in types))
        print("-" * (22 + 16 * len(types)))
        for name in strategies:
            row = f"{name:<22}"
            for t in types:
                vals = results[name]["by_type"].get(t, [])
                row += f"{(sum(vals) / len(vals) if vals else 0):>16.3f}"
            print(row)

    if args.sweep:
        print(f"\nFusion constant sweep — Recall@{args.k} and MRR")
        print(f"{'k':>6}{'Recall':>12}{'MRR':>10}")
        print("-" * 28)
        for rrf_k in (5, 10, 20, 40, 60, 100):
            swept = evaluate(
                cur, questions, embed_query,
                {"hybrid": lambda c, q, v, kk=rrf_k:
                    R.search_hybrid(c, q, v, top_k=args.k, rrf_k=kk)},
                args.k)
            r = swept["hybrid"]
            print(f"{rrf_k:>6}{r['recall_at_k']:>12.3f}{r['mean_rr']:>10.3f}")
        print("\n  The published value of 60 comes from TREC experiments, not from")
        print("  10-K filings. This table is what should decide it.")

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "k": args.k, "rrf_k": C.RRF_K,
            "answerable": results["_answerable"],
            "unanswerable": results["_unanswerable"],
            "strategies": {
                name: {
                    "recall_at_k": results[name]["recall_at_k"],
                    "mean_rr": results[name]["mean_rr"],
                    "coverage": results[name]["coverage"],
                    "n": results[name]["n"],
                    # Per type, because the aggregate hid two opposite behaviours
                    # for most of this project: the lexical path wins on
                    # comparatives and loses badly on extractive questions.
                    "recall_by_type": {
                        t: sum(v) / len(v)
                        for t, v in results[name]["by_type"].items() if v
                    },
                    "coverage_by_type": {
                        t: sum(v) / len(v)
                        for t, v in results[name]["cov_by_type"].items() if v
                    },
                }
                for name in strategies
            },
        }
        args.save.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"\nSaved to {args.save}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
