#!/usr/bin/env python3
"""
Measure generation: does the system answer when it can, and refuse when it cannot.

    python src/evaluate_generation.py --runs 3
    python src/evaluate_generation.py --runs 1 --provider echo    # free dry run
    python src/evaluate_generation.py --no-judge                  # skip groundedness

WHAT IS MEASURED, AND WHY IT COMES IN PAIRS

    Refusal rate          on unanswerable questions -- should be high
    False refusal rate    on answerable questions   -- should be low

Either metric alone is trivially gamed. A system that replies INSUFFICIENT_CONTEXT
to everything scores a perfect refusal rate and is useless; one that always
answers scores a perfect false refusal rate and invents freely. Only the pair
says anything.

    Hallucination rate    answered an unanswerable question

This is the number the project exists to produce, and the one cell of the results
table that has to be zero. Everything else admits a trade-off.

    Groundedness          is each claim supported by the excerpt it cites

Judged by the same model family that produced the answer, which is a known
weakness: LLM judges reward length and tend to agree with whatever is put in
front of them. The judge prompt is written to counter both -- it is shown the
cited excerpt and asked a yes/no question about support, not asked to rate
quality. Judged results should still be spot-checked by hand, and the results
page says so.

WHY THREE RUNS

Current models reject temperature=0, so identical inputs can produce different
answers. A refusal rate measured once is a sample. Three runs give a range, and
where the range is wide that is itself worth reporting.
"""

from __future__ import annotations

import argparse
import hashlib
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
import generate as G  # noqa: E402

log = logging.getLogger("eval-gen")

CACHE_PATH = Path("eval/cache.json")

JUDGE_SYSTEM = """You check whether a claim is supported by the source excerpts it
cites.

You are given one claim and every excerpt it cites. The claim is SUPPORTED if the
excerpts, taken together, state it -- a claim citing three excerpts need not be
found in all three.

A claim is UNSUPPORTED if no cited excerpt states it, if an excerpt states
something different, or if it needs information none of them contains. A claim
about a company is UNSUPPORTED when every cited excerpt is about a different
company, even where the figure matches. A claim about a fiscal year is
UNSUPPORTED when the excerpts cover a different year.

Do not judge whether the claim is true in the world. Judge only whether these
excerpts support it.

Reply with JSON and nothing else:

{"verdict": "SUPPORTED"}

or

{"verdict": "UNSUPPORTED"}"""

# Enough room that the model's own reasoning cannot consume the budget before a
# verdict is emitted.
#
# The first attempt used 10 tokens, the second 32, and 18% of verdicts came back
# as empty strings both times. The judge was not answering oddly -- it was not
# answering at all, having spent its allowance thinking. An empty reply is a
# failure of the evaluator, and counting it as UNSUPPORTED would have moved a
# fifth of the corpus into a category it was never judged into.
JUDGE_MAX_TOKENS = 512

JUDGE_ERROR = "judge_error"


# ─────────────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────────────
def cache_key(question: str, excerpt_ids: list[int], run: int, model: str) -> str:
    """
    Keyed on everything that changes the answer, including the run index.

    The run index is part of the key on purpose: three runs of the same question
    must produce three separate calls, or the variance this harness exists to
    measure would be cached away.
    """
    raw = f"{model}|{run}|{question}|{','.join(map(str, excerpt_ids))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# Groundedness
# ─────────────────────────────────────────────────────────────────────
def split_claims(text: str) -> list[tuple[str, list[int]]]:
    """Sentences carrying at least one citation, paired with what they cite."""
    out = []
    for sentence in G._SENTENCE_SPLIT.split(text):
        cites = [int(m) for m in G._CITATION.findall(sentence)]
        if cites and len(sentence.split()) > 3:
            out.append((sentence.strip(), cites))
    return out


def judge_claim(provider, claim: str, excerpts: list[tuple[str, str]]
                ) -> tuple[str, str]:
    """
    One verdict per claim, judged against all of its citations at once.

    Judging each citation separately was wrong and inflated the unsupported
    count. A claim citing [2][3][10] with its figure in excerpt 2 was scored
    unsupported twice -- once for 3, once for 10 -- while being perfectly
    supported. Measured on the Under Armour revenue question, where the figure and
    the year-over-year change were both exactly right.

    Returns (verdict, raw reply). An unreadable reply is JUDGE_ERROR, never
    UNSUPPORTED: not knowing is a different state from knowing the claim is
    unsupported, and collapsing them corrupts the metric that matters.
    """
    blocks = "\n\n".join(
        f"EXCERPT {label}:\n{text}" for label, text in excerpts)

    reply = provider.complete(
        system=JUDGE_SYSTEM,
        user=f"{blocks}\n\nCLAIM:\n{claim}",
        max_tokens=JUDGE_MAX_TOKENS,
    ).strip()

    if not reply:
        return JUDGE_ERROR, "(empty reply)"

    # JSON first, as the prompt requests; free text as a fallback, because a
    # model that adds a sentence around valid JSON has still answered.
    import json as _json
    import re as _re

    m = _re.search(r'\{[^{}]*"verdict"\s*:\s*"([A-Z_]+)"[^{}]*\}', reply)
    if m:
        v = m.group(1).upper()
        if v == "SUPPORTED":
            return "supported", reply
        if v == "UNSUPPORTED":
            return "unsupported", reply
        return JUDGE_ERROR, reply

    upper = reply.upper()
    # UNSUPPORTED contains SUPPORTED, so order matters.
    if "UNSUPPORTED" in upper or "NOT SUPPORTED" in upper:
        return "unsupported", reply
    if "SUPPORTED" in upper:
        return "supported", reply
    return JUDGE_ERROR, reply


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Measure refusal and groundedness")
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("-k", type=int, default=C.RETRIEVAL_TOP_K)
    ap.add_argument("--provider")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", default="eval/results/generation.json", type=Path)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "httpcore", "anthropic", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    from llm import get_provider
    from search import embed_query
    import retrieve as R
    import labels as L

    provider = get_provider(args.provider)
    model = os.environ.get("GENERATION_MODEL", provider.name)
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    # Labels are resolved against the corpus rather than read as bare ids. The
    # gold_chunk_ids written into each record below are what review_generation
    # and evaluate_correctness compare against, so a stale label would travel
    # silently into both.
    questions = L.load(args.questions)
    label_problems = L.resolve(cur, questions)
    if label_problems:
        log.error("%d gold label(s) no longer hold — run src/verify_labels.py:",
                  len(label_problems))
        for p in label_problems[:8]:
            log.error("  %-7s %s  %s", p["id"], p["kind"], p["detail"])

    cache = {} if args.no_cache else load_cache()
    cache_hits = calls = 0
    records = []

    log.info("%d questions x %d runs, provider %s, model %s",
             len(questions), args.runs, provider.name, model)
    log.info("cache %s, judge %s\n",
             "off" if args.no_cache else f"on ({len(cache)} entries)",
             "off" if args.no_judge else "on")

    started = time.time()
    failed = []
    for i, q in enumerate(questions, 1):
        qv = embed_query(q["question"])
        hits = R.search(cur, q["question"], qv, top_k=args.k)
        excerpt_ids = [h.chunk_id for h in hits]

        for run in range(args.runs):
            key = cache_key(q["question"], excerpt_ids, run, model)
            if key in cache:
                text = cache[key]
                cache_hits += 1
            else:
                try:
                    text = provider.complete(
                        system=G.SYSTEM_PROMPT,
                        user=G.build_user_message(q["question"], hits),
                        max_tokens=C.MAX_ANSWER_TOKENS,
                    ).strip()
                except Exception as exc:
                    # One question failing after its retries is not a reason to
                    # discard the other forty-nine. It is recorded and excluded,
                    # and the count is printed so the figures are not read as
                    # covering questions that never ran.
                    log.warning("  %s run %d failed: %s", q["id"], run,
                                type(exc).__name__)
                    failed.append((q["id"], run, type(exc).__name__))
                    continue
                cache[key] = text
                calls += 1

            cited, problems = G.verify_citations(text, len(hits))
            # G.is_refusal, not a substring test. The two disagreed and
            # the metric used the weaker one: a response refusing in
            # prose was counted as an answer, inflating the one figure
            # that has to be zero.
            refused = G.is_refusal(text)

            records.append({
                "id": q["id"], "type": q["type"], "answerable": q["answerable"],
                "run": run, "text": text, "refused": refused,
                "cited": cited, "problems": problems,
                "excerpt_ids": excerpt_ids,
                "gold_chunk_ids": q.get("gold_chunk_ids") or [],
            })

        mark = "refused" if records[-1]["refused"] else "answered"
        expect = "should refuse" if not q["answerable"] else "should answer"
        flag = ""
        if q["answerable"] and records[-1]["refused"]:
            flag = "  <-- false refusal"
        if not q["answerable"] and not records[-1]["refused"]:
            flag = "  <-- HALLUCINATION"
        log.info("  %-6s %-26s %-9s %s%s", q["id"], q["type"][:25], mark, expect, flag)

        # Saved after every question rather than every tenth call. A run that
        # dies at question 47 should lose one question's work, not ten.
        if calls:
            save_cache(cache)

    save_cache(cache)

    # ── Groundedness, on answers only ────────────────────────────────
    judged = defaultdict(int)
    if not args.no_judge:
        log.info("\nJudging groundedness, one verdict per claim")
        chunk_cache: dict[int, tuple] = {}

        def chunk_info(chunk_id: int) -> tuple[str, str]:
            if chunk_id not in chunk_cache:
                cur.execute("""select c.content, d.company, d.fiscal_year,
                                      c.item_section
                               from chunks c join documents d using (doc_id)
                               where c.chunk_id = %s""", (chunk_id,))
                chunk_cache[chunk_id] = cur.fetchone()
            content, company, year, section = chunk_cache[chunk_id]
            return f"({company}, FY{year}, {section})", content

        for rec in records:
            if rec["refused"] or not rec["cited"]:
                continue
            for claim, cites in split_claims(rec["text"]):
                # Every citation on this claim, gathered before judging. Judging
                # them one at a time was the bug: a claim supported by one of its
                # three sources scored unsupported twice.
                excerpts, valid, invalid = [], [], []
                for c in cites:
                    if 1 <= c <= len(rec["excerpt_ids"]):
                        valid.append(c)
                        excerpts.append(chunk_info(rec["excerpt_ids"][c - 1]))
                    else:
                        invalid.append(c)

                if invalid:
                    judged["invalid citation"] += 1
                if not excerpts:
                    continue

                verdict, raw = judge_claim(provider, claim, excerpts)
                judged[verdict] += 1
                calls += 1
                rec.setdefault("judged", []).append({
                    "claim": claim, "cited": valid,
                    "chunk_ids": [rec["excerpt_ids"][c - 1] for c in valid],
                    "sources": [label for label, _ in excerpts],
                    "verdict": verdict, "raw": raw,
                })

    # ── Results ──────────────────────────────────────────────────────
    answerable = [r for r in records if r["answerable"]]
    unanswerable = [r for r in records if not r["answerable"]]

    def rate(rows, pred):
        return sum(1 for r in rows if pred(r)) / len(rows) if rows else 0.0

    refusal = rate(unanswerable, lambda r: r["refused"])
    false_refusal = rate(answerable, lambda r: r["refused"])
    hallucination = rate(unanswerable, lambda r: not r["refused"])

    print(f"\n{'=' * 70}")
    print(f"{len(records)} responses  ·  {calls} API calls  ·  "
          f"{cache_hits} from cache  ·  {time.time() - started:.0f}s")
    print("=" * 70)

    print(f"\n{'':<34}{'answerable':>13}{'unanswerable':>15}")
    print(f"{'':<34}{len(answerable):>13}{len(unanswerable):>15}")
    print("-" * 62)
    print(f"{'answered':<34}"
          f"{rate(answerable, lambda r: not r['refused']):>13.1%}"
          f"{hallucination:>15.1%}")
    print(f"{'refused':<34}{false_refusal:>13.1%}{refusal:>15.1%}")

    print(f"\n  refusal rate on unanswerable   {refusal:>7.1%}   target: high")
    print(f"  false refusal on answerable    {false_refusal:>7.1%}   target: low")
    print(f"  HALLUCINATION RATE             {hallucination:>7.1%}   target: zero")

    # Per type: the adversarial questions are the ones written to bait an answer,
    # and burying them in the aggregate would hide the only number that matters.
    print(f"\n{'type':<28}{'n':>5}{'refused':>10}{'answered':>10}")
    print("-" * 53)
    by_type = defaultdict(list)
    for r in records:
        by_type[r["type"]].append(r)
    for t in sorted(by_type):
        rows = by_type[t]
        print(f"{t:<28}{len(rows):>5}"
              f"{rate(rows, lambda r: r['refused']):>10.1%}"
              f"{rate(rows, lambda r: not r['refused']):>10.1%}")

    # Variance across runs: without temperature=0 a single run is a sample.
    if args.runs > 1:
        flips = 0
        for qid in {r["id"] for r in records}:
            runs = [r["refused"] for r in records if r["id"] == qid]
            if len(set(runs)) > 1:
                flips += 1
        print(f"\n  {flips} of {len(set(r['id'] for r in records))} questions "
              f"changed their refusal decision between runs")
        if flips:
            print("  Without temperature=0 a single run is a sample, not a constant.")

    if judged:
        # Judge failures are reported apart from verdicts and excluded from the
        # rate. A groundedness figure computed over attempts rather than over
        # decisions understates itself by however often the judge failed, and
        # that is not a property of the system being measured.
        decided = judged.get("supported", 0) + judged.get("unsupported", 0)
        errors = judged.get(JUDGE_ERROR, 0)
        invalid = judged.get("invalid citation", 0)
        attempts = decided + errors

        print(f"\n{'groundedness':<28}{'n':>6}{'share of decided':>19}")
        print("-" * 53)
        for verdict in ("supported", "unsupported"):
            n = judged.get(verdict, 0)
            print(f"{verdict:<28}{n:>6}{(n / decided if decided else 0):>18.1%}")
        print("-" * 53)
        print(f"{'claims judged':<28}{decided:>6}")
        print(f"{'judge failures':<28}{errors:>6}"
              f"{(errors / attempts if attempts else 0):>18.1%}  of attempts")
        if invalid:
            print(f"{'invalid citations':<28}{invalid:>6}"
                  f"{'':>18}  claims citing a missing excerpt")

        print("\n  Judged by the same model family that wrote the answers.")
        print("  Spot-check a sample by hand before quoting these.")
        if errors and errors / attempts > 0.02:
            print(f"\n  {errors / attempts:.1%} of judge calls failed. Inspect them")
            print("  with src/review_generation.py --show judge-raw before")
            print("  quoting the figure above.")

    bad_citations = [r for r in records if r["problems"]]
    if bad_citations:
        print(f"\n  {len(bad_citations)} responses failed citation verification:")
        for r in bad_citations[:6]:
            print(f"    {r['id']} run {r['run']}: {r['problems'][0][:60]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": datetime.now().isoformat(timespec="seconds"),
        "model": model, "runs": args.runs, "top_k": args.k,
        "refusal_rate": refusal, "false_refusal_rate": false_refusal,
        "hallucination_rate": hallucination,
        "groundedness": dict(judged),
        "groundedness_note": (
            "One verdict per claim, judged against all of its citations at once. "
            "Judge failures are counted separately and excluded from the rate: an "
            "unreadable verdict is not evidence a claim is unsupported."
        ),
        "records": records,
    }, indent=1), encoding="utf-8")
    if failed:
        print(f"\n  {len(failed)} calls failed after retries and are excluded:")
        for qid, run, err in failed[:8]:
            print(f"    {qid} run {run}: {err}")
        print("  Re-run to fill them in; the cache keeps everything already paid for.")

    print(f"\nSaved to {args.out}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
