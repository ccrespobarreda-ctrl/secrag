#!/usr/bin/env python3
"""
Which keyword expression actually fires, and how often.

    python src/diagnose_keyword.py

The AND-first rule was added after one query returned seven of eight results
from a single unrelated filing. Measured over the labeled questions, the "keyword"
strategy and the "or-keyword" degradation score identically -- same Recall, same
MRR -- which means the rule changes nothing.

Two explanations, and they call for opposite responses:

  AND never fires. The threshold is wrong and the rule is dead code.
  AND always fires but returns the same chunks. The rule works and is redundant.

This counts which.
"""
from __future__ import annotations
import logging, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set")
        return 2

    import psycopg2, yaml
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    questions = yaml.safe_load(Path(C.EVAL_QUESTIONS).read_text(encoding="utf-8"))
    answerable = [q for q in questions if q.get("answerable")]

    print(f"{'question':<8}{'AND hits':>10}{'OR hits':>10}  expression  same top-8?")
    print("-" * 62)

    n_and = n_or = n_same = 0
    for q in answerable:
        text = q["question"]
        cur.execute(f"select count(*) from chunks c where c.content_tsv @@ {R._AND_TSQUERY}",
                    {"q": text})
        and_hits = cur.fetchone()[0]
        cur.execute(f"select count(*) from chunks c where c.content_tsv @@ {R._OR_TSQUERY}",
                    {"q": text})
        or_hits = cur.fetchone()[0]

        uses_and = and_hits >= R.KEYWORD_MIN_AND_HITS
        n_and += uses_and
        n_or += not uses_and

        a = [h.chunk_id for h in R.search_keyword(cur, text, expression=R._AND_TSQUERY)]
        o = [h.chunk_id for h in R.search_keyword(cur, text, expression=R._OR_TSQUERY)]
        same = a == o
        n_same += same

        print(f"{q['id']:<8}{and_hits:>10,}{or_hits:>10,}  "
              f"{'AND' if uses_and else 'OR ':<11} {'yes' if same else 'no'}")

    total = len(answerable)
    print(f"\n{n_and} of {total} questions use AND, {n_or} fall back to OR")
    print(f"{n_same} of {total} return an identical top-8 either way")

    if n_and == 0:
        print("\nAND never fires. The threshold of "
              f"{R.KEYWORD_MIN_AND_HITS} is never met, so the rule is dead code.")
    elif n_same == total:
        print("\nThe rule fires but changes no result. It is redundant here.")
    else:
        print("\nThe rule changes results on some questions without moving the "
              "aggregate metric. Worth keeping only if those questions matter.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
