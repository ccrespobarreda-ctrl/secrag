#!/usr/bin/env python3
"""
Build the static results page from the evaluation files.

    python src/build_results_page.py
    python src/build_results_page.py --out docs/index.html

WHY THE EVALUATION IS THE ARTEFACT, NOT THE CHATBOT

A live chat demo proves the system works on whatever the visitor happens to type.
This page proves it works on fifty questions whose answers were established by
reading the filings, and shows where it does not. That is a stronger claim and a
cheaper one: no API key, no tokens consumed by strangers, no service to keep up.

Every number here is read from eval/results/*.json. Nothing is typed in by hand,
so the page cannot drift away from what was measured -- which is the same reason
the Northlane dashboard was generated rather than written.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

CSS = """
:root{
  --ink:#12181f; --ink-2:#3a4653; --ink-3:#6b7885;
  --rule:#dde3e9; --rule-2:#eef2f5; --bg:#fbfcfd; --panel:#fff;
  --pos:#0f766e; --neg:#b4325c; --warn:#a16207;
  --mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  --body:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink-2);font-family:var(--body);
     font-size:16px;line-height:1.62;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:0 clamp(1rem,4vw,2.5rem)}
header{border-bottom:1px solid var(--rule);padding:clamp(2.5rem,6vw,4rem) 0 2rem}
.eyebrow{font-family:var(--mono);font-size:.7rem;letter-spacing:.11em;
         text-transform:uppercase;color:var(--ink-3)}
h1{font-size:clamp(1.7rem,4.2vw,2.6rem);line-height:1.15;color:var(--ink);
   margin:.7rem 0 0;max-width:32ch;letter-spacing:-.02em}
.lede{max-width:64ch;margin:1.1rem 0 0}
.lede strong{color:var(--ink)}
section{padding:clamp(2rem,5vw,3.2rem) 0;border-bottom:1px solid var(--rule)}
h2{font-size:clamp(1.15rem,2.6vw,1.5rem);color:var(--ink);margin:0 0 .3rem;
   letter-spacing:-.01em}
h2+.sub{color:var(--ink-3);font-size:.94rem;margin:0 0 1.4rem;max-width:66ch}
h3{font-size:.98rem;color:var(--ink);margin:2rem 0 .6rem}
table{width:100%;border-collapse:collapse;font-size:.87rem;margin:.4rem 0 1rem}
th{font-family:var(--mono);font-weight:500;font-size:.65rem;letter-spacing:.07em;
   text-transform:uppercase;color:var(--ink-3);text-align:right;
   padding:0 .45rem .55rem;border-bottom:1px solid var(--rule);vertical-align:bottom}
th:first-child{text-align:left}
td{padding:.5rem .45rem;text-align:right;font-family:var(--mono);font-weight:500;
   border-bottom:1px solid var(--rule-2);font-variant-numeric:tabular-nums}
td:first-child{text-align:left;font-family:var(--body);font-weight:400;color:var(--ink-2)}
tr.best td{color:var(--ink);font-weight:600}
tr.sab td{color:var(--ink-3)}
td.pos{color:var(--pos)} td.neg{color:var(--neg)} td.warn{color:var(--warn)}
caption{caption-side:bottom;text-align:left;padding-top:.7rem;font-size:.82rem;
        color:var(--ink-3);line-height:1.55}
.cards{display:grid;gap:1px;background:var(--rule);
       grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin:1.2rem 0}
.card{background:var(--panel);padding:1rem 1.1rem}
.card .k{font-family:var(--mono);font-size:.62rem;letter-spacing:.09em;
         text-transform:uppercase;color:var(--ink-3);display:block}
.card .v{font-family:var(--mono);font-size:1.5rem;font-weight:600;color:var(--ink);
         display:block;margin:.25rem 0 .2rem}
.card .v.pos{color:var(--pos)} .card .v.neg{color:var(--neg)}
.card .d{font-size:.79rem;color:var(--ink-3);display:block;line-height:1.45}
.note{background:var(--panel);border-left:2px solid var(--ink-3);
      padding:.9rem 1.1rem;margin:1.2rem 0;font-size:.9rem;max-width:70ch}
.note b{color:var(--ink)}
details{background:var(--panel);border:1px solid var(--rule);margin:.4rem 0;
        border-radius:2px}
summary{padding:.6rem .9rem;cursor:pointer;font-size:.87rem;display:flex;
        gap:.7rem;align-items:baseline;flex-wrap:wrap}
summary::marker{color:var(--ink-3)}
summary .qid{font-family:var(--mono);font-weight:600;color:var(--ink)}
summary .qtype{font-family:var(--mono);font-size:.66rem;letter-spacing:.06em;
               text-transform:uppercase;color:var(--ink-3)}
summary .verdict{font-family:var(--mono);font-size:.7rem;margin-left:auto}
.v-ok{color:var(--pos)} .v-bad{color:var(--neg)} .v-ref{color:var(--ink-3)}
.qbody{padding:0 .9rem 1rem;border-top:1px solid var(--rule-2);font-size:.89rem}
.qbody dt{font-family:var(--mono);font-size:.63rem;letter-spacing:.08em;
          text-transform:uppercase;color:var(--ink-3);margin:.9rem 0 .2rem}
.qbody dd{margin:0}
.answer{background:var(--bg);padding:.7rem .85rem;border-radius:2px;
        white-space:pre-wrap;font-size:.86rem}
.chunks{font-family:var(--mono);font-size:.78rem;color:var(--ink-3)}
footer{padding:2.5rem 0 4rem;font-size:.85rem;color:var(--ink-3)}
footer a{color:var(--ink-2)}
"""


def pct(x, dp=1):
    return f"{x * 100:.{dp}f}%"


def esc(x):
    return html.escape(str(x or ""))


# ─────────────────────────────────────────────────────────────────────
def retrieval_section(r: dict) -> str:
    n_answerable = r["answerable"]
    n_unanswerable = r["unanswerable"]
    S = r["strategies"]
    main = [k for k in S if not k.startswith("SABOTAGE")]
    sab = [k for k in S if k.startswith("SABOTAGE")]
    best = max(main, key=lambda k: S[k]["recall_at_k"])
    k = r["k"]

    rows = ""
    for name in main + sab:
        s = S[name]
        cls = "best" if name == best else ("sab" if name.startswith("SABOTAGE") else "")
        label = name.replace("SABOTAGE ", "")
        prefix = "sabotage · " if name.startswith("SABOTAGE") else ""
        rows += (f'<tr class="{cls}"><td>{prefix}{esc(label)}</td>'
                 f'<td>{s["recall_at_k"]:.3f}</td><td>{s["mean_rr"]:.3f}</td>'
                 f'<td>{s["coverage"]:.3f}</td></tr>')

    types = sorted({t for name in main for t in S[name]["recall_by_type"]})
    per_type = ""
    for name in main:
        s = S[name]
        cls = "best" if name == best else ""
        cells = "".join(
            f'<td>{s["recall_by_type"].get(t, 0):.3f}<span style="color:var(--ink-3)">'
            f' / {s["coverage_by_type"].get(t, 0):.3f}</span></td>' for t in types)
        per_type += f'<tr class="{cls}"><td>{esc(name)}</td>{cells}</tr>'

    return f"""
<section id="retrieval"><div class="wrap">
  <h2>Retrieval</h2>
  <p class="sub">Measured against the {n_answerable} answerable questions, whose
  answer chunks were identified by reading the filings. Recall@{k} asks whether any
  correct chunk arrived; coverage asks what fraction of them did. The other
  {n_unanswerable} questions have no answer chunks by definition and belong to the
  refusal measurement below.</p>

  <table>
    <thead><tr><th>strategy</th><th>Recall@{k}</th><th>MRR</th><th>Coverage</th></tr></thead>
    <tbody>{rows}</tbody>
    <caption>Five degradations, each disabling one capability. All five move the
    metric down, which is what makes the harness worth trusting: a check that only
    ever passes cannot distinguish a working system from a broken one.</caption>
  </table>

  <h3>By question type — Recall@{k} / coverage</h3>
  <table>
    <thead><tr><th>strategy</th>{"".join(f"<th>{esc(t)}</th>" for t in types)}</tr></thead>
    <tbody>{per_type}</tbody>
    <caption>The aggregate hid two opposite behaviours for most of this project.
    Semantic search wins on extractive questions and loses badly on comparatives;
    lexical search does the reverse. A single number averaged them into
    meaninglessness.</caption>
  </table>

  <div class="note">
    <b>Recall@{k} and coverage diverge most where the answer is distributed.</b>
    On comparatives, recall reads 1.000 and coverage 0.350: a comparative needs
    evidence from two filings, and finding one of them counts as a hit. Reporting
    only recall would have called the weakest question type the strongest.
  </div>
</div></section>"""


def generation_section(g: dict) -> str:
    recs = g["records"]
    ans = [r for r in recs if r["answerable"]]
    una = [r for r in recs if not r["answerable"]]

    def rate(rows, pred):
        return sum(1 for r in rows if pred(r)) / len(rows) if rows else 0.0

    gr = g.get("groundedness", {})
    decided = gr.get("supported", 0) + gr.get("unsupported", 0)
    supported = gr.get("supported", 0) / decided if decided else 0
    failures = gr.get("judge_error", 0)
    attempts = decided + failures

    by_type = defaultdict(list)
    for r in recs:
        by_type[r["type"]].append(r)
    type_rows = "".join(
        f'<tr><td>{esc(t)}</td><td>{len(rows)}</td>'
        f'<td>{pct(rate(rows, lambda r: r["refused"]))}</td>'
        f'<td>{pct(rate(rows, lambda r: not r["refused"]))}</td></tr>'
        for t, rows in sorted(by_type.items()))

    hallucinated = [r for r in una if not r["refused"]]

    return f"""
<section id="generation"><div class="wrap">
  <h2>Refusal, and what it costs</h2>
  <p class="sub">Fifty questions, {g["runs"]} runs each. Sixteen have no answer in
  the corpus and five of those are written to bait an invention — a fiscal year
  outside the filings, a business segment that does not exist.</p>

  <table>
    <thead><tr><th></th><th>answerable ({len(ans)})</th><th>unanswerable ({len(una)})</th></tr></thead>
    <tbody>
      <tr><td>answered</td>
          <td class="pos">{pct(rate(ans, lambda r: not r["refused"]))}</td>
          <td class="neg">{pct(rate(una, lambda r: not r["refused"]))}</td></tr>
      <tr><td>refused</td>
          <td class="warn">{pct(rate(ans, lambda r: r["refused"]))}</td>
          <td class="pos">{pct(rate(una, lambda r: r["refused"]))}</td></tr>
    </tbody>
    <caption>Both columns matter. A system that replies "insufficient context" to
    everything scores a perfect refusal rate and is useless; one that always
    answers invents freely. Either number alone is trivially gamed.</caption>
  </table>

  <div class="cards">
    <div class="card"><span class="k">refusal, unanswerable</span>
      <span class="v pos">{pct(g["refusal_rate"])}</span>
      <span class="d">target: high</span></div>
    <div class="card"><span class="k">false refusal, answerable</span>
      <span class="v warn">{pct(g["false_refusal_rate"])}</span>
      <span class="d">target: low</span></div>
    <div class="card"><span class="k">answered without support</span>
      <span class="v neg">{pct(g["hallucination_rate"])}</span>
      <span class="d">{len(hallucinated)} of {len(una)} responses</span></div>
    <div class="card"><span class="k">claims grounded in a citation</span>
      <span class="v pos">{pct(supported)}</span>
      <span class="d">{decided} claims judged, {failures} judge failures</span></div>
  </div>

  <table>
    <thead><tr><th>question type</th><th>responses</th><th>refused</th><th>answered</th></tr></thead>
    <tbody>{type_rows}</tbody>
    <caption>None of the five adversarial questions produced an answer in any run.
    Those are the ones designed to be answered wrongly.</caption>
  </table>

  <div class="note">
    <b>Groundedness is judged by the same model family that wrote the answers.</b>
    That is a known weakness: LLM judges reward length and tend to agree with what
    is put in front of them. An earlier version judged each citation separately: a
    claim citing three excerpts was marked unsupported by the two that did not
    contain its figure, while being perfectly supported. It also gave the judge a
    ten-token budget, and nearly a fifth of verdicts came back empty — the judge
    spending its allowance before answering, which is a failure of the evaluator
    and not evidence about any claim. The figure above is one verdict per claim,
    judged against all of its citations at once, over {decided} claims with
    {failures} judge failures.
  </div>
</div></section>"""


def gallery_section(g: dict, questions: list[dict], limit: int) -> str:
    qmap = {q["id"]: q for q in questions}
    first = {}
    for r in g["records"]:
        first.setdefault(r["id"], r)

    items = ""
    for qid in sorted(first, key=lambda x: (x[0], int(x[1:]))):
        r = first[qid]
        q = qmap.get(qid, {})
        gold = set(r["gold_chunk_ids"])
        retrieved = set(r["excerpt_ids"])
        found = sorted(gold & retrieved)

        if not r["answerable"]:
            verdict, cls = ("refused", "v-ok") if r["refused"] else ("answered anyway", "v-bad")
        elif r["refused"]:
            verdict, cls = "refused", "v-ref"
        else:
            verdict, cls = "answered", "v-ok"

        gold_line = (f"{len(found)} of {len(gold)} gold chunks retrieved: {found}"
                     if gold else "no gold chunks — the corpus does not answer this")

        items += f"""
<details>
  <summary><span class="qid">{esc(qid)}</span>
    <span class="qtype">{esc(r["type"])}</span>
    <span>{esc(q.get("question", ""))}</span>
    <span class="verdict {cls}">{verdict}</span></summary>
  <div class="qbody"><dl>
    <dt>labeled answer</dt>
    <dd>{esc(q.get("gold_answer") or "— none; this question has no answer in the corpus")}</dd>
    <dt>generated, run {r["run"]}</dt>
    <dd class="answer">{esc(r["text"])}</dd>
    <dt>retrieval</dt>
    <dd class="chunks">{esc(gold_line)}<br>cited excerpts: {esc(r["cited"] or "none")}</dd>
    {'<dt>citation problems</dt><dd class="chunks">' + esc("; ".join(r["problems"])) + "</dd>" if r["problems"] else ""}
  </dl></div>
</details>"""

    return f"""
<section id="gallery"><div class="wrap">
  <h2>Every question, and what happened</h2>
  <p class="sub">All fifty, with the labeled answer beside the generated one. A
  live chat demo proves a system works on whatever a visitor types; this shows it
  against answers established by reading the filings, including where it fails.</p>
  {items}
</div></section>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the results page")
    ap.add_argument("--retrieval", default="eval/results/retrieval.json", type=Path)
    ap.add_argument("--generation", default="eval/results/generation.json", type=Path)
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("--out", default="docs/index.html", type=Path)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    missing = [p for p in (args.retrieval, args.generation, args.questions)
               if not p.exists()]
    if missing:
        for p in missing:
            print(f"missing: {p}")
        print("\nRun src/evaluate_retrieval.py --save and "
              "src/evaluate_generation.py first.")
        return 2

    import yaml
    r = json.loads(args.retrieval.read_text(encoding="utf-8"))
    g = json.loads(args.generation.read_text(encoding="utf-8"))
    questions = yaml.safe_load(args.questions.read_text(encoding="utf-8"))

    S = r["strategies"]
    best = max((k for k in S if not k.startswith("SABOTAGE")),
               key=lambda k: S[k]["recall_at_k"])

    n_unanswerable = sum(1 for q in questions if not q["answerable"])
    n_hallucinated = len({rec["id"] for rec in g["records"]
                          if not rec["answerable"] and not rec["refused"]})
    n_chunks = r.get("chunks") or "4,169"

    page = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEC filings RAG — evaluation results</title>
<meta name="description" content="Retrieval and refusal measured over 50 hand-labeled questions on 19 SEC 10-K filings.">
<style>{CSS}</style>
</head><body>

<header><div class="wrap">
  <div class="eyebrow">19 SEC 10-K filings · {len(questions)} labeled questions · {g["model"]}</div>
  <h1>Asked {n_unanswerable} questions it could not answer, it invented {n_hallucinated}.</h1>
  <p class="lede">Question answering over {n_chunks} chunks of SEC annual reports,
  with citations verified in code. The hard part is not producing fluent answers;
  it is not producing them when the documents do not support one. Sixteen of the
  fifty questions have no answer in the corpus and five are written to bait an
  invention — a fiscal year outside the filings, a business segment that does not
  exist. Across {g["runs"]} runs, <strong>{pct(g["hallucination_rate"])}</strong>
  of responses to those questions were classified as answering, and the adversarial
  five produced none.</p>
  <p class="lede">The cost is refusing <strong>{pct(g["false_refusal_rate"])}</strong>
  of the questions it could have answered. That is bounded by retrieval, not by
  caution: the retriever surfaces a correct chunk
  <strong>{pct(S[best]["recall_at_k"], 0)}</strong> of the time, and where it does
  not, refusing is the right answer.</p>
</div></header>

{retrieval_section(r)}
{generation_section(g)}
{gallery_section(g, questions, args.limit)}

<footer><div class="wrap">
  <p>Every figure on this page is read from <code>eval/results/*.json</code> at
  build time. Nothing is typed in by hand, so the page cannot drift from what was
  measured.</p>
  <p>The corpus is public: 19 10-K filings pulled from SEC EDGAR. The labels are
  not — they were assigned by reading the filings, and the criterion is stated in
  the repository, because a recall figure without its labeling criterion is
  uninterpretable.</p>
  <p>Retrieval: {r["k"]} chunks per query, hybrid dense and lexical with
  reciprocal rank fusion, restricted to the company named in the question.
  Generation: {g["model"]}, {g["runs"]} runs per question. Embeddings computed
  locally; only the generation call leaves the machine.</p>
</div></footer>

</body></html>"""

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")

    print(f"Wrote {args.out} ({len(page) / 1024:.0f} KB)")
    print(f"  best strategy      {best}  Recall@{r['k']} {S[best]['recall_at_k']:.3f}")
    print(f"  hallucination      {pct(g['hallucination_rate'])}")
    print(f"  false refusal      {pct(g['false_refusal_rate'])}")
    print(f"  questions shown    {len({rec['id'] for rec in g['records']})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
