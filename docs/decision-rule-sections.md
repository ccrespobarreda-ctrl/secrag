# Does correcting the section boundaries produce better answers?

**Written before the run, and not edited afterwards.** The point of a decision
rule is that it is fixed while the result is still unknown; a rule adjusted after
seeing the numbers is a description of the numbers.

This is the second such rule in the project. The first,
`docs/decision-rule-ordering.md`, decided whether better ordering produces better
answers and returned an interval spanning zero, which was published as the
result.

**This one is not blind, and the difference matters.** That rule was written
before any of its numbers existed. This one is written knowing that retrieval
moved from 0.735 to 0.794 in favour of the corrected corpus. A rule written with
one result already in hand is weaker than one written with none — the direction
of the partial evidence is known to whoever writes it, and it can shape what
counts as a win without anyone intending it. It is still worth writing, because
the generation figures are not in and those are what it decides. It is recorded
here as what it is rather than presented as the equal of the first.

## The question

Commit `4001782` fixed the section boundaries on 14 August. Finding 18 shows its
output never reached the warehouse: the reload happened at 18:30, the corrected
`chunks.json` was written at 19:39, and every published figure was measured over
the corpus that preceded it. 115 of 4,124 shared positions carry a different
`item_section` — `Item 3` where the corrected parse says `Item 7`, `Item 7` where
it says `Item 7A`.

`item_section` is read in five places in `src/retrieve.py` and three in
`src/search.py`. It drives the `--section` filter and the provenance label every
excerpt carries into the prompt, so the model has been told the wrong Item for
some of what it was shown.

**Retrieval is already measured**: 0.735 on the uncorrected corpus against 0.794
on the corrected one, both with the labels that belong to each. Two questions out
of 34, intervals overlapping over most of their width. That figure is in and
cannot be unseen, which is exactly why the rest is decided here rather than
afterwards.

## What decides it

**Answer correctness against the labelled answer.** Not groundedness.

Groundedness is conditional on the excerpts that arrived. A model told the right
Item may say more and be judged on more claims; one told the wrong Item may
hedge, say less, and cite what it does say perfectly. Groundedness would reward
the second. It measures honesty about the material at hand, not usefulness.

Refusal on unanswerable questions, false refusal and groundedness are
guardrails: they can stop this, they do not decide it.

## The rule

Both corpora, the same 50-question regression split, the same questions, the
same code, three runs each, generated fresh. Analysis is **paired**: the same
questions on both sides, differences per question, every question that changes
verdict named. Two aggregate rates over 34 answerable questions have little
power; the paired differences have more, and they say *where* the change is.

**Correctness is judged on all three runs of each corpus, not on run 0.** In
August it was judged on one run, on the grounds that three near-identical
answers triple the cost for little. That holds when the question is "how good is
this system" and fails when it is "do these two differ": a difference of one or
two questions cannot be told from run-to-run noise by a single run on each side.
Judging three gives a per-question rate in [0, 1/3, 2/3, 1] on both sides, and
the paired difference is taken on those.

The noise is known for refusal and unknown for correctness. Across the 70
questions of the August file, **refusal changes between runs on zero of them**,
three runs each. That is why the statistical weight below sits on correctness
and the refusal guardrails can be read as counts.

**Which split, and why both sides are measured.** The generation figures in the
README come from `vnext_generation_promptv2_judge2.json`, and that file holds
**70 questions, not 100**: it is the regression+development split. The
correctness figure comes from a different file, a different date and 34
questions. Neither is a measurement of the 50-question regression split, so
neither can be compared against a new run of it. **Both corpora are measured
here, on the same split, in the same session.** Reusing August's numbers as one
side of the comparison would reintroduce exactly the confusion finding 17 is
about.

| | Value | Source |
|---|---:|---|
| Refusal on unanswerable | 100% | `vnext_generation_promptv2_judge2.json`, 20 Aug, **70 questions** |
| False refusal | 0% | same |
| Hallucination | 0% | same |
| Correctness | 91.2% | `correctness_final_rrf40_run0.json`, 17 Aug, 34 questions |

These are context, not the comparison. The comparison is the two runs made here.

**The corrected corpus is adopted regardless of the correctness result.** The
boundaries were wrong; correcting a defect does not have to earn its place with
a gain. What the result decides is what gets *claimed*, and there are three
outcomes:

- **Corrected leads by more than the paired interval.** Then the section
  boundaries were costing answers, the README says so and names the questions
  it wins.

- **The interval spans zero.** Then correcting them does not measurably change
  answers at this sample size. That is the result, it is published as the
  result, and it is not read as support for whichever number is higher —
  including when the higher number is the new one and retrieval already moved
  in its favour.

- **Corrected is worse.** Then it is published as worse, with the questions it
  loses named, and the corpus is adopted anyway. Reverting a correct parse
  because the figures preferred the incorrect one is the one move this project
  cannot make.

**What stops it.** Not a comparison against zero. 0% false refusal is 0 of 34,
whose 95% interval reaches 10%: one question changing is inside the noise of the
figure it would be compared against, and a rule that stops on it stops on noise.

The condition is stated on the pair, on the same questions, in the same session:

- **any question that the uncorrected corpus answers and the corrected one
  refuses** is named and read before publication. One is a case to understand;
  the release continues.
- **three or more such questions**, or **any question unanswerable in the
  benchmark that the corrected corpus answers**, stops the release. Refusal on
  unanswerable questions has never moved in this project — zero flips across 70
  questions and three runs — so a single one of those is not noise, it is a
  behaviour change.

Neither sends the corpus back. They stop the release until the cause is known.

**And if correctness rises while false refusal rises with it**, which is
possible — a model told the right Item may answer more and decline less — the
stop takes precedence over the gain. Three new refusals stop the release even
when correctness is clearly better, because the two are not on the same footing:
correctness is a measurement over 34 questions with an interval, and a refusal
on a question the system used to answer is a behaviour, visible one question at
a time. A rule that let a favourable aggregate override a named behaviour change
would be the aggregate hiding the case, which is the defect `score_one` in
`src/evaluate_retrieval.py` exists to prevent on the retrieval side.

## The order, and what a half-finished run is worth

**The uncorrected corpus is measured first**, in the same session, before the
warehouse is reloaded — it is the one currently loaded, and reloading is what
destroys it. Then the corrected one. Both sides use the same question file, the
same code and the same provider, and `measured_against` in each result file
records which corpus, how many chunks and which labels.

**A run that finishes on one side only is not published.** Not as a partial
result, not as a comparison against August's figures, not as a note. One side
alone is a measurement of a corpus, not of a difference, and this project has
spent two days establishing what happens when a figure from one corpus is set
beside a figure from another.

## What is not measured here

**The holdout.** It was spent in August: one run, figures published, not touched
again. A new corpus makes it technically unused, and that is precisely the
reasoning to distrust — a reserve is spent when there is a decision to make, not
when there is budget. There is no decision here it could settle: retrieval is
already measured, and what generation does is answerable on the regression
split.

**The 0.794.** It is in and it is not evidence about answers. Retrieval bounds
generation and does not determine it; the whole reason `evaluate_correctness.py`
exists is that a perfectly grounded answer can still state the wrong fact.

## What this costs

50 questions × 3 runs × 2 corpora for generation, and correctness judged on all
three runs of each rather than on one: 34 answerable × 3 × 2 = 204 judge calls
where August made 34. Roughly 15–20 € at the rates the earlier runs were
measured under, against the 10–15 € this document first estimated when it
planned to judge one run.
`eval/cache.json` is copied first. The cache will not help: its key includes the
excerpt ids, and a reloaded corpus reissues every one of them, so both sides are
paid in full.
