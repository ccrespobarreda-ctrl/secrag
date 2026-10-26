#!/usr/bin/env python3
"""
Ask the AI Act corpus the demo questions with the unchanged SEC pipeline.

    python portfolio_aiact/ask.py                 # the questions in QUESTIONS
    python portfolio_aiact/ask.py "any question"

Retrieval, prompt rules, refusal marker and citation verification are
src/retrieve.py and src/generate.py as they are. Four things are adjusted at
runtime, without editing those files, because they name the old corpus:

  - the first line of the system prompt says "SEC 10-K filings"
  - rule 5 talks about amounts in filings
  - excerpt labels carry a fiscal year, which a regulation does not have
  - company detection is switched off: there are no companies here

Results are written to portfolio_aiact/results.json for the portfolio video.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import generate as G  # noqa: E402
import retrieve as R  # noqa: E402

# (question, the article that answers it). The third has no answer in the
# Regulation and must be refused.
QUESTIONS = [
    ("When does the AI Act start to apply, and which parts apply earlier?", "Article 113"),
    ("What fines apply for non-compliance with the prohibited AI practices?", "Article 99"),
    ("What fine did the European Commission impose on OpenAI under the AI Act?", None),
]

old = "You answer questions about SEC 10-K filings"
assert old in G.SYSTEM_PROMPT, "generate.SYSTEM_PROMPT changed; update ask.py"
G.SYSTEM_PROMPT = G.SYSTEM_PROMPT.replace(
    old, "You answer questions about the EU Artificial Intelligence Act "
         "(Regulation (EU) 2024/1689)")
G.SYSTEM_PROMPT = G.SYSTEM_PROMPT.replace(
    "Filings state\n   amounts in thousands or millions; do not convert.",
    "Do not convert\n   amounts or dates.")
R.Hit.label = lambda self: "(" + ", ".join(
    p for p in [self.company, self.item_section, self.section_title] if p) + ")"
R.detect_companies = lambda question: []


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set"); return 2
    import psycopg2
    from llm import get_provider

    provider = get_provider(None)
    cur = psycopg2.connect(os.environ["DATABASE_URL"]).cursor()
    questions = [(q, None) for q in sys.argv[1:]] or QUESTIONS
    results = []

    for q, expected in questions:
        t0 = time.time()
        a = G.answer_question(cur, provider, q)
        secs = time.time() - t0
        bar = "-" * 78
        print(f"\nquestion   {q!r}\nprovider   {provider.name}\n\n{bar}\nANSWER\n{bar}\n")
        print(a.text)
        print(f"\n{bar}\nSOURCES\n{bar}")
        for i in a.cited:
            print(f"  [{i}] {a.excerpts[i - 1].label()}")
        print(f"\n{bar}\nVERIFICATION\n{bar}")
        print(f"  refused          {a.refused}")
        print(f"  excerpts sent    {len(a.excerpts)}")
        print(f"  citations        {a.cited or 'none'}")
        print(f"  problems         {a.problems or 'none'}")
        print(f"  seconds          {secs:.2f}")
        if expected:
            found = any(h.item_section == expected for h in a.excerpts)
            print(f"  {expected} retrieved: {'yes' if found else 'NO'}")
        results.append({
            "question": q, "expected": expected, "provider": provider.name,
            "model": getattr(provider, "model", None), "answer": a.text,
            "refused": a.refused, "cited": a.cited, "problems": a.problems,
            "seconds": round(secs, 2),
            "excerpts": [{"n": i, "label": h.label(), "chunk_id": h.chunk_id,
                          "content": h.content}
                         for i, h in enumerate(a.excerpts, 1)],
        })

    out = Path(__file__).resolve().parent / "results.json"
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(results)} answers to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
