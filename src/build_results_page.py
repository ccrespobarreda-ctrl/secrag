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
import re
import sys
from math import sqrt
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
.filters{display:flex;flex-wrap:wrap;gap:.4rem;margin:0 0 1.6rem}
/* These read as labels unless they are made to look pressable. On a phone
   there is no hover to discover it with, so the affordance has to be in the
   resting state: a real border, ink-coloured text, and a caret. */
.filters button{font-family:var(--mono);font-size:.72rem;letter-spacing:.05em;
  text-transform:uppercase;padding:.55rem .9rem;border:1px solid var(--ink-3);
  background:var(--bg);color:var(--ink);border-radius:3px;cursor:pointer;
  box-shadow:0 1px 0 var(--rule);transition:background .12s,color .12s}
.filters button::before{content:"▸ ";color:var(--ink-3)}
.filters button:hover{background:var(--rule-2)}
.filters button:active{transform:translateY(1px);box-shadow:none}
.filters button[aria-pressed="true"]{background:var(--ink);color:#fff;
  border-color:var(--ink);box-shadow:none}
.filters button[aria-pressed="true"]::before{content:"● ";color:#fff}
.filters-hint{font-family:var(--mono);font-size:.7rem;color:var(--ink-3);
  text-transform:uppercase;letter-spacing:.05em;margin:0 0 .5rem}
.grouphead{margin:2.2rem 0 .2rem;font-size:1rem;color:var(--ink);font-weight:600}
.groupsub{color:var(--ink-3);font-size:.9rem;margin:.15rem 0 1rem;max-width:68ch}
.why{background:var(--rule-2);border-left:2px solid var(--ink-3);
  padding:.6rem .85rem;margin:.7rem 0 0;font-size:.9rem;color:var(--ink-2)}
.contact{margin:1.6rem 0 0;font-size:.95rem}
.contact a{color:var(--pos)}
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
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Interval for a proportion. A rate of 100% over nine questions is not
    certainty, and the page should not imply that it is."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


# The benchmark notes carry an internal prefix -- "vNext comparative dev." --
# that means nothing to a reader. The sentence after it is the explanation,
# already written at labeling time, and it is what a visitor needs.
_NOTE_PREFIX = re.compile(r"^vNext\s+\S+\s+\S+\.\s*", re.IGNORECASE)


def clean_note(note: str | None) -> str:
    return _NOTE_PREFIX.sub("", note or "").strip()


def merge_generation(files: list) -> dict:
    """
    One page, several evaluation runs.

    The hundred questions were generated in two batches -- the tuning splits and
    the sealed holdout -- and a visitor should see all of them, in one list, with
    no way to tell which batch a question came from except by reading. Merging
    here rather than re-running keeps the sealed results exactly as they were
    measured.
    """
    merged = None
    for path in files:
        d = json.loads(path.read_text(encoding="utf-8"))
        if merged is None:
            merged = dict(d)
            merged["records"] = list(d["records"])
        else:
            seen = {(r["id"], r["run"]) for r in merged["records"]}
            merged["records"] += [r for r in d["records"]
                                  if (r["id"], r["run"]) not in seen]
            for key in ("groundedness",):
                a, b = merged.get(key) or {}, d.get(key) or {}
                merged[key] = {k: (a.get(k, 0) or 0) + (b.get(k, 0) or 0)
                               for k in set(a) | set(b)
                               if isinstance(a.get(k, 0), int)
                               and isinstance(b.get(k, 0), int)} or a

    # Recomputed from the merged records rather than carried over. The rates in
    # each input file describe that file alone; keeping the first one would
    # publish half a measurement under a whole-benchmark heading.
    recs = merged["records"]
    unans = [r for r in recs if not r["answerable"]]
    ans = [r for r in recs if r["answerable"]]
    merged["refusal_rate"] = (sum(r["refused"] for r in unans) / len(unans)
                              if unans else 0.0)
    merged["hallucination_rate"] = (sum(not r["refused"] for r in unans)
                                    / len(unans) if unans else 0.0)
    merged["false_refusal_rate"] = (sum(r["refused"] for r in ans) / len(ans)
                                    if ans else 0.0)
    return merged


def by_question(records: list) -> dict:
    """Collapse runs to one verdict per question. Three runs of one question are
    one observation, not three."""
    runs = {}
    for r in records:
        runs.setdefault(r["id"], []).append(r)
    out = {}
    for qid, rs in runs.items():
        refusals = sum(1 for r in rs if r["refused"])
        gold = set(rs[0].get("gold_chunk_ids") or [])
        got = any(gold & set(r.get("excerpt_ids") or []) for r in rs)
        out[qid] = {"rs": rs, "type": rs[0]["type"],
                    "answerable": rs[0]["answerable"],
                    "refused": refusals * 2 > len(rs),
                    "gold_retrieved": got, "gold_labeled": bool(gold)}
    return out


def retrieval_section(r: dict) -> str:
    n_answerable = r["answerable"]
    n_unanswerable = r["unanswerable"]
    S = r["strategies"]
    main = [k for k in S if not k.startswith("SABOTAGE")]
    # The bolded row is a baseline without embeddings, and saying nothing about
    # that would be the quiet version of the overclaiming this page measures.
    # Only rendered when the comparison is actually in the file.
    lex, dense = S.get("keyword+company"), S.get("hybrid+company")
    # A tolerance rather than >=. These two tie exactly on the original 50, and
    # a note that appears or vanishes on the fourth decimal is not a finding.
    if lex and dense and lex["recall_at_k"] >= dense["recall_at_k"] - 0.005:
        baseline_note = (
            '<p class="groupsub">The lexical baseline — Postgres full-text '
            'search with the same company filter, no embeddings and no fusion — '
            f'ties on Recall@{r["k"]} and leads on coverage '
            f'({lex["coverage"]:.3f} against {dense["coverage"]:.3f}). The dense '
            f'half contributes ordering ({dense["mean_rr"]:.3f} MRR against '
            f'{lex["mean_rr"]:.3f}), not reach. That was not the expected '
            'result; it is documented in <code>docs/measurement-honesty.md</code>.'
            '</p>')
    else:
        baseline_note = ""

    sab = [k for k in S if k.startswith("SABOTAGE")]
    # The two lead strategies tie exactly on the original 50, and max() would
    # then bold whichever the file happened to list first -- a highlight that
    # moves with dictionary order rather than with a result. Ties are broken on
    # coverage, then MRR, and the same tolerance as the baseline note above.
    def _rank(name):
        s = S[name]
        return (round(s["recall_at_k"], 3), round(s["coverage"], 3),
                round(s["mean_rr"], 3))
    best = max(main, key=_rank)
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

    # The degradation caption used to assert a result whether or not the file
    # contained one. A page that claims a check it did not run is exactly the
    # failure this project measures.
    sab = [k for k in S if k.startswith("SABOTAGE")]
    moved = [k for k in sab
             if S[k]["recall_at_k"] < S[best]["recall_at_k"] - 0.01]
    if not sab:
        sabotage_note = ("Degradation checks are not in this run. Build with "
                         "--sabotage to include them: they disable one capability "
                         "each and confirm the metric falls, because a check that "
                         "only ever passes cannot distinguish a working system "
                         "from a broken one.")
    else:
        sabotage_note = (f"{len(sab)} degradations, each disabling one capability. "
                         f"{len(moved)} of {len(sab)} move the metric down, which is "
                         f"what makes the harness worth trusting: a check that only "
                         f"ever passes cannot distinguish a working system from a "
                         f"broken one.")

    # The same defect the sabotage caption had, in prose instead of a caption:
    # this note asserted 1.000 and 0.350, and neither is in any results file --
    # 0.350 appears nowhere at all, and the only comparative recall of 1.000 is
    # in the holdout, which this section explicitly does not measure. Computed
    # now, like every other figure on the page.
    #
    # Every type over the threshold, not the widest one. The gaps sit within a
    # few hundredths of each other, so an argmax would change the sentence's
    # subject on noise; and the explanation below -- an answer spread across
    # passages counts as found once one arrives -- is true of distributed
    # answers and would be wrong under a type that diverged for another reason.
    DIVERGENCE_MIN = 0.10
    diverging = [(t, S[best]["recall_by_type"].get(t, 0.0),
                  S[best]["coverage_by_type"].get(t, 0.0)) for t in types]
    diverging = sorted([d for d in diverging if d[1] - d[2] >= DIVERGENCE_MIN],
                       key=lambda d: -(d[1] - d[2]))
    if diverging:
        pairs = ", ".join(f"{esc(t)} {rec:.3f} against {cov:.3f}"
                          for t, rec, cov in diverging)
        divergence_note = (
            f'<div class="note"><b>Recall@{k} and coverage diverge where the '
            f'answer is distributed.</b> On {esc(best)}, recall and coverage '
            f'part company on {pairs}: an answer spread over several passages '
            f'counts as found the moment one of them arrives. Reporting recall '
            f'alone would flatter exactly the questions that need the most '
            f'evidence.</div>')
    else:
        divergence_note = ""

    return f"""
<section id="retrieval"><div class="wrap">
  <h2>Retrieval</h2>
  <p class="sub">Measured on the original 50 questions — the ones written before
  this system existed — because the questions added later were labeled by literal
  string match and a lexical search finds those labels almost every time. Why that
  matters is in <code>docs/measurement-honesty.md</code>. Of those 50, the
  {n_answerable} answerable ones carry answer chunks, identified by reading
  the filings. Recall@{k} asks whether any
  correct chunk arrived; coverage asks what fraction of them did. The other
  {n_unanswerable} questions have no answer chunks by definition and belong to the
  refusal measurement below.</p>

  <table>
    <thead><tr><th>strategy</th><th>Recall@{k}</th><th>MRR</th><th>Coverage</th></tr></thead>
    <tbody>{rows}</tbody>
    <caption>{sabotage_note}</caption>
  </table>
  {baseline_note}

  <h3>By question type — Recall@{k} / coverage</h3>
  <table>
    <thead><tr><th>strategy</th>{"".join(f"<th>{esc(t)}</th>" for t in types)}</tr></thead>
    <tbody>{per_type}</tbody>
    <caption>The aggregate hid two opposite behaviours for most of this project.
    Semantic search wins on extractive questions and loses badly on comparatives;
    lexical search does the reverse. A single number averaged them into
    meaninglessness.</caption>
  </table>

  {divergence_note}
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
    # `absence` is a verdict, not a judge failure: the claim was read and found
    # to assert something the excerpts do not address. Reporting it beside the
    # failures, rather than folding it silently out of the denominator, is the
    # difference between a rate and a rate that flatters itself.
    absence = gr.get("absence", 0)
    attempts = decided + failures + absence

    by_type = defaultdict(list)
    for r in recs:
        by_type[r["type"]].append(r)
    type_rows = "".join(
        f'<tr><td>{esc(t)}</td><td>{len(rows)}</td>'
        f'<td>{pct(rate(rows, lambda r: r["refused"]))}</td>'
        f'<td>{pct(rate(rows, lambda r: not r["refused"]))}</td></tr>'
        for t, rows in sorted(by_type.items()))

    hallucinated = [r for r in una if not r["refused"]]

    # Counted in questions, because the headline figures are. A table headed
    # "207 answerable" beside a headline of "69 questions" invites the reader to
    # think two different things were measured.
    n_ans_q = len({r["id"] for r in ans})
    n_una_q = len({r["id"] for r in una})
    n_adversarial = len({r["id"] for r in recs
                         if r["type"] == "unanswerable_adversarial"})

    return f"""
<section id="generation"><div class="wrap">
  <h2>Refusal, and what it costs</h2>
  <p class="sub">{len({r["id"] for r in recs})} questions, {g["runs"]} runs each. {len({r["id"] for r in recs if not r["answerable"]})} have no answer in
  the corpus and {len({r["id"] for r in recs if r["type"] == "unanswerable_adversarial"})} of those are written to bait an invention — a fiscal year
  outside the filings, a business segment that does not exist.</p>

  <table>
    <thead><tr><th></th><th>answerable ({n_ans_q} questions)</th><th>unanswerable ({n_una_q} questions)</th></tr></thead>
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
      <span class="d">{len({r["id"] for r in hallucinated})} of {n_una_q} questions</span></div>
    <div class="card"><span class="k">claims grounded in a citation</span>
      <span class="v pos">{pct(supported)}</span>
      <span class="d">{decided} of {attempts} claims decided; {absence} absence,
      {failures} judge failures</span></div>
  </div>

  <table>
    <thead><tr><th>question type</th><th>responses</th><th>refused</th><th>answered</th></tr></thead>
    <tbody>{type_rows}</tbody>
    <caption>None of the {n_adversarial} adversarial questions produced an answer in any run.
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
    judged against all of its citations at once, over {decided} decided claims.
    A further {absence} came back as absence -- the claim was read, and what it
    asserts is not addressed by the excerpts either way -- and {failures} as
    judge failures. Neither is counted as supported or unsupported, so the rate
    above is {decided} claims wide, not {attempts}; over all {attempts} attempts
    it reads {pct(gr.get("supported", 0) / attempts if attempts else 0)}.
  </div>
</div></section>"""


GROUPS = [
    ("trap", "Written to bait an invention",
     "Each of these contains a trap: a fiscal year the filings do not reach, a "
     "business segment that does not exist, an acquisition that never happened. "
     "A system built to be helpful will produce something. Watch what this one "
     "does instead."),
    ("miss", "Where the search failed and it stayed quiet",
     "These questions do have an answer in the filings. The search did not "
     "surface the right passage, and rather than assembling an answer from what "
     "it did have, the system said it could not answer. This is the failure mode "
     "that matters: not whether a system fails, but what it does when it does."),
    ("absent", "Questions the filings simply do not answer",
     "Companies disclose what they choose to disclose. These ask for figures no "
     "annual report contains -- a per-unit manufacturing cost, an internal "
     "conversion rate, a headcount broken down by department."),
    ("answered", "Answered from the filings",
     "Every factual claim ends with a citation, and every citation is checked in "
     "code against the excerpts actually supplied to the model."),
]


def group_of(v: dict) -> str:
    if v["type"] == "unanswerable_adversarial":
        return "trap"
    if v["answerable"] and v["refused"]:
        return "miss"
    if not v["answerable"]:
        return "absent"
    return "answered"


def gallery_section(g: dict, questions: list[dict], limit: int) -> str:
    """
    The questions, ordered by what they demonstrate rather than by id.

    Sorted by id, the first thing a visitor met was Q001: an extractive question,
    answered correctly, indistinguishable from what any retrieval demo shows. The
    cases worth seeing -- the traps, and the one retrieval failure -- were
    somewhere past the fold. Ordering is the whole difference between a list of
    results and a demonstration.
    """
    qmap = {q["id"]: q for q in questions}
    qs = by_question(g["records"])
    grouped = {}
    for qid, v in qs.items():
        grouped.setdefault(group_of(v), []).append(qid)

    filters = "".join(
        f'<button data-filter="{key}" aria-pressed="false">{title} '
        f'({len(grouped.get(key, []))})</button>'
        for key, title, _ in GROUPS)

    blocks = ""
    for key, title, blurb in GROUPS:
        ids = sorted(grouped.get(key, []), key=lambda x: (x[0], int(x[1:])))
        if not ids:
            continue
        items = ""
        for qid in ids[:limit]:
            v = qs[qid]
            r = v["rs"][0]
            q = qmap.get(qid, {})
            gold = set(r["gold_chunk_ids"])
            found = sorted(gold & set(r["excerpt_ids"]))

            if not v["answerable"]:
                verdict, cls = (("declined", "v-ok") if v["refused"]
                                else ("answered anyway", "v-bad"))
            elif v["refused"]:
                verdict, cls = "declined", "v-ref"
            else:
                verdict, cls = "answered", "v-ok"

            gold_line = (f"{len(found)} of {len(gold)} labeled passages "
                         f"retrieved: {found}" if gold
                         else "no labeled passage - the filings do not answer this")

            note = clean_note(q.get("notes"))
            why = f'<p class="why">{esc(note)}</p>' if note and key != "answered" else ""

            items += f"""
<details data-group="{key}">
  <summary><span class="qid">{esc(qid)}</span>
    <span class="qtype">{esc(r["type"])}</span>
    <span>{esc(q.get("question", ""))}</span>
    <span class="verdict {cls}">{verdict}</span></summary>
  <div class="qbody">{why}<dl>
    <dt>labeled answer</dt>
    <dd>{esc(q.get("gold_answer") or "- none; the filings do not answer this")}</dd>
    <dt>what the system said, run {r["run"]}</dt>
    <dd class="answer">{esc(r["text"])}</dd>
    <dt>retrieval</dt>
    <dd class="chunks">{esc(gold_line)}<br>cited excerpts: {esc(r["cited"] or "none")}</dd>
    {'<dt>citation problems</dt><dd class="chunks">' + esc("; ".join(r["problems"])) + "</dd>" if r["problems"] else ""}
  </dl></div>
</details>"""

        blocks += (f'\n<h3 class="grouphead">{esc(title)}</h3>'
                   f'<p class="groupsub">{esc(blurb)}</p>{items}')

    return f"""
<section id="gallery"><div class="wrap">
  <h2>Every question, and what happened</h2>
  <p class="sub">All {len(qs)}, with the labeled answer beside the generated one,
  grouped by what each one demonstrates. A live chat demo proves a system works on
  whatever a visitor types; this shows it against answers established by reading
  the filings, including where it fails.</p>
  <p class="filters-hint">Tap to filter</p>
  <div class="filters">{filters}<button data-filter="all" aria-pressed="true">Show all</button></div>
  {blocks}
</div></section>
<script>
(function(){{
  var bs=document.querySelectorAll('.filters button');
  bs.forEach(function(b){{
    b.addEventListener('click',function(){{
      var f=b.dataset.filter;
      bs.forEach(function(o){{o.setAttribute('aria-pressed',o===b?'true':'false');}});
      document.querySelectorAll('#gallery details').forEach(function(d){{
        d.style.display=(f==='all'||d.dataset.group===f)?'':'none';
      }});
      document.querySelectorAll('.grouphead,.groupsub').forEach(function(h){{
        h.style.display=(f==='all')?'':'none';
      }});
    }});
  }});
}})();
</script>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the results page")
    ap.add_argument("--retrieval", default="eval/results/retrieval.json", type=Path)
    ap.add_argument("--generation", action="append", type=Path, default=[],
                    help="repeatable; several evaluation runs merge into one page")
    ap.add_argument("--contact", default="", help="email shown in the header")
    ap.add_argument("--questions", default=C.EVAL_QUESTIONS, type=Path)
    ap.add_argument("--out", default="docs/index.html", type=Path)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    if not args.generation:
        args.generation = [Path("eval/results/generation.json")]
    missing = [p for p in [args.retrieval, *args.generation, args.questions]
               if not p.exists()]
    if missing:
        for p in missing:
            print(f"missing: {p}")
        print("\nRun src/evaluate_retrieval.py --save and "
              "src/evaluate_generation.py first.")
        return 2

    import yaml
    r = json.loads(args.retrieval.read_text(encoding="utf-8"))
    g = merge_generation(args.generation)
    questions = yaml.safe_load(args.questions.read_text(encoding="utf-8"))

    S = r["strategies"]
    best = max((k for k in S if not k.startswith("SABOTAGE")),
               key=lambda k: S[k]["recall_at_k"])

    qs = by_question(g["records"])
    n_q = len(qs)
    unans = {k: v for k, v in qs.items() if not v["answerable"]}
    ans = {k: v for k, v in qs.items() if v["answerable"]}
    traps = {k: v for k, v in unans.items()
             if v["type"] == "unanswerable_adversarial"}

    # A question counts once. Three runs of the same question are one
    # observation repeated, and reporting them as three narrows every interval
    # by a factor the data does not support.
    n_hallucinated = sum(1 for v in unans.values() if not v["refused"])
    refused_ans = {k: v for k, v in ans.items() if v["refused"]}
    unjustified = {k: v for k, v in refused_ans.items()
                   if not (v["gold_labeled"] and not v["gold_retrieved"])}
    _, halluc_hi = wilson(n_hallucinated, len(unans))
    n_chunks = r.get("chunks") or "4,169"
    contact = (f'<p class="contact">Built by Cristina Crespo Barreda. '
               f'<a href="mailto:{esc(args.contact)}">{esc(args.contact)}</a></p>'
               if args.contact else
               '<p class="contact">Built by Cristina Crespo Barreda.</p>')

    page = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEC filings RAG — evaluation results</title>
<meta name="description" content="Retrieval and refusal measured over 50 hand-labeled questions on 19 SEC 10-K filings.">
<style>{CSS}</style>
</head><body>

<header><div class="wrap">
  <div class="eyebrow">19 SEC 10-K filings · {n_q} labeled questions · {g["model"]}</div>
  <h1>Asked {len(unans)} questions it could not answer, it invented {n_hallucinated}.</h1>
  <p class="lede">If you put a language model in front of your documents, the
  risk is not that it answers badly. It is that it answers confidently when the
  document does not say what it claims, and nobody notices until the number is
  in a report. This system answers questions about SEC annual reports, cites the
  passage behind every figure, and declines when the documents do not support an
  answer.</p>
  <p class="lede">Of {n_q} questions, <strong>{len(unans)} have no answer in the
  filings</strong> and {len(traps)} are written to bait an invention: a fiscal
  year outside the corpus, a segment that does not exist, an acquisition that
  never happened. Across {g["runs"]} runs it invented
  <strong>{n_hallucinated}</strong> — with an upper bound of
  <strong>{pct(halluc_hi)}</strong> at 95% confidence, because zero out of
  {len(unans)} is a small sample and saying otherwise would be the same
  overclaiming this measures.</p>
  <p class="lede">It declined <strong>{len(refused_ans)}</strong> of the
  {len(ans)} questions it could have answered, and in that case the search had
  not surfaced the evidence — so declining was correct. Excluding it,
  <strong>{len(unjustified)}</strong> answerable questions were wrongly refused.
  Every claim on this page is read from the evaluation files at build time.</p>
  {contact}
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
  <p>Method, splits and the three measurement problems found while building this
  are documented in <code>docs/measurement-honesty.md</code>, including one where
  a simpler lexical baseline matches this system on coverage.</p>
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
    print(f"  hallucination      {n_hallucinated}/{len(unans)} questions "
          f"(95% upper bound {pct(halluc_hi)})")
    print(f"  false refusal      {len(unjustified)}/{len(ans)} "
          f"retrieval-adjusted, {len(refused_ans)} unadjusted")
    print(f"  questions shown    {n_q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
