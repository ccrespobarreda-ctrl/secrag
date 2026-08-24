#!/usr/bin/env python3
"""
Measure what one question costs and how long it takes.

    python src/measure_cost.py --dry-run
    python src/measure_cost.py
    python src/measure_cost.py --repeats 3 --save eval/results/cost_latency.json

WHY THIS IS NOT READ OFF THE EVALUATION RUN

The generation harness reports wall time for a whole batch, and that batch
includes a groundedness judge call per claim. Dividing it by the number of
questions answers a question nobody asked. What a buyer wants to know is what
happens when one person asks one thing: how long until an answer appears, and
what that answer cost.

So this times the two halves separately. Retrieval is embedding plus two SQL
queries and a fusion, entirely local, and costs nothing. Generation is one API
call, and it is the whole bill.

WHAT IS AND IS NOT INCLUDED

The embedding model is loaded before timing starts. A first query that includes
model load takes several seconds more, and reporting that as query latency would
overstate it for every subsequent question in a running service.

Token counts come from the API response rather than from an estimate, so the cost
figure is arithmetic on measured usage rather than a guess about prompt size.
Prices are not hardcoded: rates change, a stale constant would silently produce a
wrong number, and the token counts are the durable measurement. Pass --price-in
and --price-out from current pricing to convert.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import generate as G  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("cost")

# A spread rather than a convenient one. An extractive question against a single
# filing is the cheapest thing the system does; a comparative pulls from two and
# fills the excerpt budget, and an unanswerable one ends in a refusal, which is
# short. Reporting only the first would understate every other question.
QUESTIONS = [
    ("extractive", "What were Under Armour's net revenues in fiscal 2026?"),
    ("multi_chunk", "What segments does Levi Strauss report, and how did each "
                    "perform?"),
    ("comparative", "Which reports higher net revenues, Crocs or Deckers "
                    "Outdoor?"),
    ("unanswerable", "What were Wayfair's net revenues for fiscal 2030?"),
]


def usage_of(response) -> tuple[int, int]:
    u = getattr(response, "usage", None)
    return (getattr(u, "input_tokens", 0) or 0,
            getattr(u, "output_tokens", 0) or 0)


def timed_answer(cur, provider, question: str, embed):
    """One question, with the two halves timed apart and tokens captured."""
    t0 = time.perf_counter()
    qv = embed(question)
    hits = R.search(cur, question, qv, top_k=C.RETRIEVAL_TOP_K)
    t1 = time.perf_counter()

    # The provider interface returns text, not the response object, so the call
    # is made directly here to reach usage. Same model, same parameters.
    resp = provider.client.messages.create(
        model=provider.model,
        max_tokens=C.MAX_ANSWER_TOKENS,
        system=G.SYSTEM_PROMPT,
        messages=[{"role": "user",
                   "content": G.build_user_message(question, hits)}],
    )
    t2 = time.perf_counter()

    text = "".join(b.text for b in resp.content
                   if getattr(b, "type", "") == "text")
    tin, tout = usage_of(resp)
    return {
        "retrieval_s": t1 - t0,
        "generation_s": t2 - t1,
        "total_s": t2 - t0,
        "input_tokens": tin,
        "output_tokens": tout,
        "excerpts": len(hits),
        "refused": G.is_refusal(text),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure per-query cost and latency")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--provider", default=None)
    ap.add_argument("--price-in", type=float,
                    help="currency per million input tokens")
    ap.add_argument("--price-out", type=float,
                    help="currency per million output tokens")
    ap.add_argument("--save", type=Path)
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be called, call nothing")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    n_calls = len(QUESTIONS) * args.repeats
    if args.dry_run:
        print(f"would ask {len(QUESTIONS)} questions × {args.repeats} repeats "
              f"= {n_calls} API calls\n")
        for kind, q in QUESTIONS:
            print(f"  {kind:<14}{q}")
        print("\nNothing called.")
        return 0

    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    from llm import get_provider
    from search import embed_query

    provider = get_provider(args.provider)
    if not hasattr(provider, "client"):
        log.error("Provider %r has no client to read token usage from. "
                  "Use anthropic or vertex.", provider.name)
        return 2

    # Loaded before the clock starts, so the first question is not charged for it.
    print("loading the embedding model")
    embed_query("warm up")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    print(f"\n{n_calls} calls, provider {provider.name}, model {provider.model}\n")
    rows = []
    for kind, question in QUESTIONS:
        for i in range(args.repeats):
            m = timed_answer(cur, provider, question, embed_query)
            m["type"] = kind
            m["question"] = question
            rows.append(m)
            print(f"  {kind:<14}run {i}  retrieval {m['retrieval_s']:5.2f}s  "
                  f"generation {m['generation_s']:5.2f}s  "
                  f"{m['input_tokens']:>6} in  {m['output_tokens']:>4} out"
                  f"{'  refused' if m['refused'] else ''}")
    conn.close()

    def stat(key):
        vals = [r[key] for r in rows]
        return statistics.median(vals), min(vals), max(vals)

    print(f"\n{'':<16}{'median':>10}{'min':>10}{'max':>10}")
    print("-" * 46)
    for label, key in (("retrieval", "retrieval_s"),
                       ("generation", "generation_s"),
                       ("total", "total_s")):
        med, lo, hi = stat(key)
        print(f"{label:<16}{med:>9.2f}s{lo:>9.2f}s{hi:>9.2f}s")

    tin = statistics.median(r["input_tokens"] for r in rows)
    tout = statistics.median(r["output_tokens"] for r in rows)
    print(f"\n{'tokens in':<16}{tin:>10.0f}   median")
    print(f"{'tokens out':<16}{tout:>10.0f}   median")

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "model": provider.model,
        "top_k": C.RETRIEVAL_TOP_K,
        "repeats": args.repeats,
        "median_retrieval_s": stat("retrieval_s")[0],
        "median_generation_s": stat("generation_s")[0],
        "median_total_s": stat("total_s")[0],
        "median_input_tokens": tin,
        "median_output_tokens": tout,
        "runs": rows,
    }

    if args.price_in and args.price_out:
        per = tin / 1e6 * args.price_in + tout / 1e6 * args.price_out
        payload["price_per_million_input"] = args.price_in
        payload["price_per_million_output"] = args.price_out
        payload["cost_per_query"] = per
        print(f"\n{'per query':<16}{per:>10.4f}   at the rates supplied")
        print(f"{'per 1,000':<16}{per * 1000:>10.2f}")
    else:
        print("\n  Pass --price-in and --price-out from current pricing to "
              "convert\n  these token counts into a cost per query.")

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"\nSaved to {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
