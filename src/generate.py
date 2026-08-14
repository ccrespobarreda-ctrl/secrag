#!/usr/bin/env python3
"""
Answer a question from retrieved excerpts, with citations verified in code.

    LLM_PROVIDER=echo python src/generate.py "any question"
    python src/generate.py "What were Under Armour's net revenues in fiscal 2026?"

THE PROMPT DOES THREE THINGS, AND ALL THREE ARE LOad-BEARING

  1. Numbers the excerpts, so a citation can be checked mechanically.
  2. Requires a citation on every factual claim.
  3. Permits refusal explicitly, with an exact marker.

The third is what makes honesty measurable. A model told only to "answer from the
context" will produce something for a question the context cannot answer, because
producing text is what it does. Given an explicit, named way out, refusing becomes
an available move — and because the marker is exact, refusal can be counted
rather than judged.

VERIFICATION IS NOT OPTIONAL

Asking for citations and trusting them is theatre. A model can cite [7] when only
five excerpts were sent, or cite [2] for a claim that appears nowhere in excerpt
2. Both are checked here:

  - every cited index exists in what was actually sent
  - every sentence containing a figure carries a citation
  - the refusal marker, when present, stands alone rather than decorating an
    answer that was given anyway

What is NOT checked here is whether the cited excerpt genuinely supports the
claim. That is groundedness, it needs a judge, and it belongs to the evaluation
harness.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

log = logging.getLogger("generate")

SYSTEM_PROMPT = f"""You answer questions about SEC 10-K filings using only the \
numbered excerpts supplied in the user message.

Rules:

1. Every factual claim must end with a citation naming the excerpt it came from,
   written as [3]. Claims combining two excerpts cite both, as [3][7].

2. If the excerpts do not contain the answer, reply with exactly:
   {C.REFUSAL_MARKER}
   on its own line, followed by one sentence naming what document or disclosure
   would contain it.

   A refusal must be clean. Do not state a figure, a percentage or an amount
   anywhere in a refusal, not even hedged, not even as "the value appears to be".
   If you know enough to name a number, you know enough to answer -- so either
   answer with a citation or refuse without the number. There is no middle
   position, and a refusal carrying a figure is worse than either: it reads as an
   answer and scores as a refusal.

3. Never use knowledge from outside the excerpts, even when you are confident and
   even when the question seems to have an obvious answer. A figure you recall
   for a company is not evidence about the fiscal year being asked about.

4. If excerpts disagree, say so and cite both rather than choosing.

5. Quote figures exactly as they appear, including units and scale. Filings state
   amounts in thousands or millions; do not convert.

Answer in at most six sentences."""


@dataclass
class Answer:
    question: str
    text: str
    excerpts: list[R.Hit]
    refused: bool = False
    cited: list[int] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def cited_chunk_ids(self) -> list[int]:
        return [self.excerpts[i - 1].chunk_id
                for i in self.cited if 1 <= i <= len(self.excerpts)]


def build_user_message(question: str, hits: list[R.Hit]) -> str:
    """
    Provenance travels with each excerpt.

    Without the company and fiscal year attached, a model shown five revenue
    tables from five filings has no way to tell which belongs to the company
    asked about, and will produce a confident answer from the wrong one.
    """
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(f"[{i}] {h.label()}\n{h.content}")
    excerpts = "\n\n".join(blocks)
    return f"EXCERPTS:\n\n{excerpts}\n\nQUESTION: {question}"


_CITATION = re.compile(r"\[(\d{1,2})\]")

# A refusal expressed in prose rather than with the marker.
#
# The exact marker exists so refusal can be counted mechanically, and it mostly
# works. But a model that reasons its way to "an exact number cannot be
# determined from these excerpts" has refused, and counting that as a
# hallucination is worse than the imprecision of matching phrases: it inflates
# the one metric that has to be zero.
#
# Measured on the Yeti question, where the model refused in prose and explicitly
# rejected the trap -- twelve countries of employees, not of sales -- and the
# harness scored it as answering a question it could not answer.
_PROSE_REFUSAL = re.compile(
    r"\b(?:do(?:es)? not (?:provide|contain|state|specify|include|give)"
    r"|cannot be determined"
    r"|is not (?:given|provided|stated|specified|disclosed)"
    r"|no (?:exact |precise |specific )?(?:count|number|figure|data|information)"
    r"\s+(?:is |of |for )?"
    r"|not (?:disclosed|available) in the excerpts"
    r"|the excerpts? (?:do|does) not)\b",
    re.IGNORECASE)
# A sentence carrying a currency amount, a percentage or a year is making a
# factual claim and needs a source.
# The percentage alternative is separate from the scale words: a trailing \b
# after % never matches, because % is not a word character and neither is the
# space that follows it. Written as one alternation with a shared \b, every
# percentage silently escaped the check.
_FIGURE = re.compile(
    r"[$€£]\s?[\d,]+"
    r"|\b\d[\d,]*\.?\d*\s?%"
    r"|\b\d[\d,]*\.?\d*\s?(?:million|billion|thousand)\b"
    r"|\b(?:19|20)\d{2}\b")

# Stricter, for use inside a refusal. A refusal legitimately names a year --
# "the excerpts cover fiscal 2026 only" is the correct thing to say, and the
# general pattern flagged it as answering. An amount or a percentage inside a
# refusal is answering; a bare year is context.
_ANSWERING_FIGURE = re.compile(
    r"[$€£]\s?[\d,]+"
    r"|\b\d[\d,]*\.?\d*\s?%"
    r"|\b\d[\d,]*\.?\d*\s?(?:million|billion|thousand)\b")
# Sentence boundaries, tolerant of the two things that broke the naive version.
#
#   1. Markdown bullets. A model asked for a list produces
#      "- **Banana Republic**: Founded in 1978 ... [2]", and splitting only on
#      terminal punctuation put the figure and its citation in different pieces.
#
#   2. Decimals and abbreviations. "$90 million (170 basis points) in Fiscal
#      2025 ... [2][7]" contains no internal period, but "Jan. 31" and "U.S."
#      do, and each one split a sentence away from its citation.
#
# Requiring a capital letter or a bullet after the boundary handles both.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[]|[-*•]\s)|\n\s*(?=[-*•]\s)")


def is_refusal(text: str) -> bool:
    """
    A refusal is a refusal when the limitation IS the answer, not when it is a
    caveat attached to one.

    Matching the phrase alone was wrong. Asked how each Gap brand performed, the
    model answered with everything the excerpts held -- net sales up $280 million,
    which brands drove it, store counts by brand -- and closed with "the excerpts
    do not provide brand-level net sales broken out individually". That is a
    partial answer with its scope declared, which is the best available response
    when the gold chunks were not retrieved. Scoring it as a refusal made two
    checks contradict each other: one reported a refusal, the other reported a
    refusal that stated figures.

    So the phrase counts only when the response is not also making cited claims.
    The exact marker always counts, because the prompt asks for it to stand alone.
    """
    if C.REFUSAL_MARKER in text:
        return True
    if not _PROSE_REFUSAL.search(text):
        return False

    # A cited factual claim before the limitation means an answer was given.
    for sentence in _SENTENCE_SPLIT.split(text):
        if _PROSE_REFUSAL.search(sentence):
            continue
        if _CITATION.search(sentence) and _FIGURE.search(sentence):
            return False
    return True


def verify_citations(text: str, n_excerpts: int) -> tuple[list[int], list[str]]:
    problems: list[str] = []
    cited = [int(m) for m in _CITATION.findall(text)]

    out_of_range = sorted({c for c in cited if c < 1 or c > n_excerpts})
    if out_of_range:
        problems.append(
            f"cited excerpt(s) {out_of_range} but only {n_excerpts} were supplied")

    refused = is_refusal(text)
    if refused:
        # A refusal that also answers is worse than either: it reads as an
        # answer while scoring as a refusal.
        stripped = text.replace(C.REFUSAL_MARKER, "").strip()
        if _ANSWERING_FIGURE.search(stripped):
            problems.append(
                "refused and still stated a figure — the marker must stand alone")
        return sorted(set(cited)), problems

    if not cited:
        problems.append("no citations at all")

    for sentence in _SENTENCE_SPLIT.split(text):
        if _FIGURE.search(sentence) and not _CITATION.search(sentence):
            problems.append(f"uncited figure: {sentence.strip()[:70]}")

    return sorted(set(cited)), problems


def answer_question(cur, provider, question: str, top_k: int = C.RETRIEVAL_TOP_K,
                    sections: list[str] | None = None,
                    embed=None) -> Answer:
    if embed is None:
        from search import embed_query
        embed = embed_query

    hits = R.search(cur, question, embed(question),
                    top_k=top_k, sections=sections)

    if not hits:
        return Answer(question=question,
                      text=f"{C.REFUSAL_MARKER}\nRetrieval returned nothing.",
                      excerpts=[], refused=True)

    text = provider.complete(
        system=SYSTEM_PROMPT,
        user=build_user_message(question, hits),
        max_tokens=C.MAX_ANSWER_TOKENS,
    ).strip()

    cited, problems = verify_citations(text, len(hits))
    return Answer(question=question, text=text, excerpts=hits,
                  refused=is_refusal(text), cited=cited,
                  problems=problems)


def main() -> int:
    ap = argparse.ArgumentParser(description="Answer a question with citations")
    ap.add_argument("question")
    ap.add_argument("-k", type=int, default=C.RETRIEVAL_TOP_K)
    ap.add_argument("--section", action="append")
    ap.add_argument("--provider", help="vertex, local or echo")
    ap.add_argument("--show-excerpts", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set")
        return 2

    import psycopg2
    from llm import get_provider

    provider = get_provider(args.provider)
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    print(f"question   {args.question!r}")
    print(f"provider   {provider.name}")

    answer = answer_question(cur, provider, args.question,
                             top_k=args.k, sections=args.section)

    if args.show_excerpts:
        print(f"\n{'-' * 78}\nEXCERPTS SENT\n{'-' * 78}")
        for i, h in enumerate(answer.excerpts, 1):
            print(f"\n  [{i}] {h.label()}  chunk {h.chunk_id}")
            print(f"      {' '.join(h.content.split())[:150]}...")

    print(f"\n{'-' * 78}\nANSWER\n{'-' * 78}\n")
    print(answer.text)

    print(f"\n{'-' * 78}\nVERIFICATION\n{'-' * 78}")
    print(f"  refused          {answer.refused}")
    print(f"  excerpts sent    {len(answer.excerpts)}")
    print(f"  citations        {answer.cited or 'none'}")
    if answer.cited_chunk_ids:
        print(f"  cited chunks     {answer.cited_chunk_ids}")

    if answer.problems:
        print(f"\n  {len(answer.problems)} problem(s):")
        for p in answer.problems:
            print(f"    {p}")
        conn.close()
        return 1

    print("\n  every citation points at an excerpt that was actually supplied,")
    print("  and no figure is stated without one")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
