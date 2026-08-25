#!/usr/bin/env python3
"""
Does a cross-encoder reranker earn its place, and its milliseconds?

    python src/experiment_rerank.py --dry-run
    python src/experiment_rerank.py
    python src/experiment_rerank.py --pool 96 --save eval/results/experiment_rerank.json

THE SHAPE OF THE PROBLEM IT SHOULD FIT

Diagnosis on the comparative questions found gold chunks sitting at ranks 17,
29, 30 and 50 — present in the corpus, found by the retriever, and cut off by a
budget of 16. That is the exact failure a reranker exists for: retrieve wide,
score precisely, keep few.

Bi-encoders embed the question and the passage separately, so the score can only
be a distance between two summaries written without knowledge of each other. A
cross-encoder reads both together and scores the pair. It is far more accurate
and far too slow to run over a whole corpus, which is why it goes second, over a
candidate pool.

WHY A SMALL MODEL, DELIBERATELY

bge-reranker-base is 280M parameters and would spend seconds on CPU scoring 64
candidates. Measured end-to-end latency for one question is 3.4s, of which
retrieval is 0.21s; adding two seconds to buy ranking quality is a bad trade in
a system whose cost and latency are published. ms-marco-MiniLM-L-6-v2 is 22M and
does the same job in tens of milliseconds. Whether the smaller model is good
enough is the question this measures rather than assumes.

WHAT IS REPORTED

Recall@16 and coverage before and after, overall and by type, with Wilson
intervals on recall. Plus the added latency, because a retrieval improvement
that doubles response time is a different decision than a free one, and the page
publishes both numbers.

src/retrieve.py is not modified. If the numbers do not justify the component, it
does not get added -- the same rule applied to the dense retriever, which lost.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import time
from collections import defaultdict
from math import sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("rerank")

MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model = None


def get_model(name: str):
    global _model
    if _model is None:
        for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3",
                      "transformers"):
            logging.getLogger(noisy).setLevel(logging.ERROR)
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(name, max_length=512, device="cpu")
    return _model


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


def bucketed_rerank(cur, question: str, qv, model, top_k: int, pool: int):
    """
    Rerank inside each company's own candidate list, then interleave.

    Reranking the merged list globally discards the per-company quota, and for a
    question naming two companies that is not a reranking experiment: it is a
    reranker without a quota against a fusion with one, two changes at once. The
    slots go to whichever company's passages the cross-encoder happens to score
    higher, which is how a comparative ends up with sixteen excerpts about one
    of the two firms.

    Here each company keeps its share and only the order within that share
    changes, which isolates what is being tested.
    """
    tickers = R.detect_companies(question)
    if len(tickers) <= 1:
        cand = R.search(cur, question, qv, top_k=pool)
        scores = model.predict([(question, h.content) for h in cand])
        return [cand[i] for i in sorted(range(len(cand)),
                                        key=lambda i: -scores[i])]

    per_pool = max(1, pool // len(tickers))
    per_out = max(1, top_k // len(tickers))
    buckets = []
    for t in tickers:
        cand = R.search_hybrid(cur, question, qv, top_k=per_pool, tickers=[t])
        if not cand:
            buckets.append([])
            continue
        scores = model.predict([(question, h.content) for h in cand])
        buckets.append([cand[i] for i in sorted(range(len(cand)),
                                                key=lambda i: -scores[i])])

    out, seen = [], set()
    for i in range(per_pool):
        for bucket in buckets:
            if i < len(bucket) and bucket[i].chunk_id not in seen:
                seen.add(bucket[i].chunk_id)
                out.append(bucket[i])
    return out


def score_set(hits, gold: set[int], k: int) -> tuple[float, float]:
    """Recall@k and coverage, matching src/evaluate_retrieval.py exactly."""
    ids = [h.chunk_id for h in hits[:k]]
    found = {i for i in ids if i in gold}
    return (1.0 if found else 0.0), (len(found) / len(gold) if gold else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure a cross-encoder reranker")
    ap.add_argument("--questions", type=Path,
                    default=Path("eval/questions_vnext_regression.yaml"))
    ap.add_argument("-k", type=int, default=C.RETRIEVAL_TOP_K)
    ap.add_argument("--pool", type=int, default=64,
                    help="candidates fetched before reranking")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--mode", choices=("global", "bucket"), default="bucket",
                    help="rerank the merged list, or inside each company's share")
    ap.add_argument("--save", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.dry_run:
        print(f"would rerank the top {args.pool} down to {args.k} with "
              f"{args.model}\n  questions: {args.questions}\n"
              f"  no API calls, no tokens; the model runs on CPU")
        return 0

    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    import labels as L
    from search import embed_query

    print(f"loading {args.model}")
    try:
        model = get_model(args.model)
    except Exception as exc:
        log.error("Could not load the reranker: %s", exc)
        log.error("It downloads from the Hugging Face hub on first use.")
        return 2

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    questions = L.load(args.questions)
    L.resolve(cur, questions)
    rows = [q for q in questions
            if q.get("answerable") and q.get("gold_chunk_ids")]
    print(f"{len(rows)} answerable questions, pool {args.pool} -> k {args.k}, "
          f"mode {args.mode}\n")

    base = {"recall": [], "cov": [], "by": defaultdict(list),
            "cov_by": defaultdict(list)}
    rr = {"recall": [], "cov": [], "by": defaultdict(list),
          "cov_by": defaultdict(list)}
    t_retrieval, t_rerank, moved = [], [], []

    for q in rows:
        gold = set(q["gold_chunk_ids"])
        qv = embed_query(q["question"])

        t0 = time.perf_counter()
        pool = R.search(cur, q["question"], qv, top_k=args.pool)
        t1 = time.perf_counter()

        if args.mode == "global":
            scores = model.predict([(q["question"], h.content) for h in pool])
            reranked = [pool[i] for i in sorted(range(len(pool)),
                                                key=lambda i: -scores[i])]
        else:
            reranked = bucketed_rerank(cur, q["question"], qv, model,
                                       args.k, args.pool)
        t2 = time.perf_counter()

        t_retrieval.append(t1 - t0)
        t_rerank.append(t2 - t1)

        # The baseline is the pool truncated at k, which is what the system
        # ships today: the same candidates, ordered by fusion instead.
        for store, hits in ((base, pool), (rr, reranked)):
            rec, cov = score_set(hits, gold, args.k)
            store["recall"].append(rec)
            store["cov"].append(cov)
            store["by"][q["type"]].append(rec)
            store["cov_by"][q["type"]].append(cov)

        for cid in gold:
            b = next((i for i, h in enumerate(pool, 1) if h.chunk_id == cid), None)
            a = next((i for i, h in enumerate(reranked, 1) if h.chunk_id == cid), None)
            if b and a and b != a:
                moved.append({"id": q["id"], "chunk_id": cid,
                              "before": b, "after": a})

    conn.close()
    n = len(rows)

    def mean(v):
        return sum(v) / len(v) if v else 0.0

    print(f"{'':<22}{'baseline':>12}{'reranked':>12}{'change':>10}")
    print("-" * 56)
    for label, key in (("Recall@%d" % args.k, "recall"), ("Coverage", "cov")):
        b, a = mean(base[key]), mean(rr[key])
        print(f"{label:<22}{b:>12.3f}{a:>12.3f}{a - b:>+10.3f}")

    kb, ka = int(sum(base["recall"])), int(sum(rr["recall"]))
    lo_b, hi_b = wilson(kb, n)
    lo_a, hi_a = wilson(ka, n)
    print(f"\n  baseline  {kb}/{n}  95% CI [{lo_b:.3f}, {hi_b:.3f}]")
    print(f"  reranked  {ka}/{n}  95% CI [{lo_a:.3f}, {hi_a:.3f}]")
    if not (ka > kb and lo_a > hi_b):
        print("  The intervals overlap. At this sample size that is expected "
              "even for a\n  real improvement; it means this alone does not "
              "settle it.")

    print(f"\n{'by type':<22}{'baseline':>12}{'reranked':>12}{'change':>10}")
    print("-" * 56)
    for t in sorted(base["cov_by"]):
        b, a = mean(base["cov_by"][t]), mean(rr["cov_by"][t])
        print(f"  {t:<20}{b:>12.3f}{a:>12.3f}{a - b:>+10.3f}"
              f"   (n={len(base['cov_by'][t])})")
    print("  coverage; recall by type in the saved file")

    mr, mk = statistics.median(t_retrieval), statistics.median(t_rerank)
    print(f"\n{'latency, median':<22}{'':>12}")
    print(f"  retrieval, pool {args.pool:<8}{mr:>10.3f}s")
    print(f"  reranking{'':<13}{mk:>10.3f}s")
    print(f"  added to a 3.40s query{'':<0}{mk / 3.40:>9.1%}")

    ups = [m for m in moved if m["after"] < m["before"]]
    print(f"\n  gold chunks moved up {len(ups)}, down {len(moved) - len(ups)}")
    for m in sorted(ups, key=lambda x: x["before"] - x["after"],
                    reverse=True)[:6]:
        print(f"    {m['id']}  chunk {m['chunk_id']:<6} "
              f"{m['before']:>3} -> {m['after']:<3}")

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps({
            "model": args.model, "k": args.k, "pool": args.pool, "n": n,
            "mode": args.mode,
            "baseline": {"recall": mean(base["recall"]),
                         "coverage": mean(base["cov"]),
                         "recall_by_type": {t: mean(v) for t, v in base["by"].items()},
                         "coverage_by_type": {t: mean(v) for t, v in base["cov_by"].items()}},
            "reranked": {"recall": mean(rr["recall"]),
                         "coverage": mean(rr["cov"]),
                         "recall_by_type": {t: mean(v) for t, v in rr["by"].items()},
                         "coverage_by_type": {t: mean(v) for t, v in rr["cov_by"].items()}},
            "median_retrieval_s": mr, "median_rerank_s": mk,
            "moved": moved}, indent=1), encoding="utf-8")
        print(f"\nSaved to {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
