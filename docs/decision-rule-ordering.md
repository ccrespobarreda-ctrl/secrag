# Does better ordering produce better answers?

**Written before the run, and not edited afterwards.** The point of a decision
rule is that it is fixed while the result is still unknown; a rule adjusted after
seeing the numbers is a description of the numbers.

## The question

Holding the company filter constant, the lexical baseline ties the full system on
Recall@16 across all four splits and leads it on coverage in two. The dense half
and the rank fusion contribute ordering — MRR 0.310 against 0.280 — and no
additional reach.

`docs/measurement-honesty.md` states that whether better ordering produces better
*answers* has not been measured, and that the generation evaluation ran on one
retrieval configuration only. This run answers that.

## What decides it

**Answer correctness against the labelled answer.** Not groundedness.

Groundedness is conditional on the excerpts that arrived. A worse retriever sends
worse excerpts, the model says less, and what it does say is cited perfectly — so
groundedness rises. It measures honesty about the material at hand, not
usefulness, and choosing on it rewards whichever branch risks least.

Correctness is measured against the answer established by reading the filing, so
it falls when the right passage does not arrive, however well the response cites
what did.

Groundedness, refusal on unanswerable questions, and false refusal are
guardrails: they can veto a winner, they do not pick one.

## The rule

Both branches run from scratch, in the same session, on the same question file,
with the same code. Nothing is compared against `vnext_generation_promptv2_judge2.json`:
that file predates yesterday's anchor changes and a change to the verification
code, which is exactly the confusion Q016 documents.

Split: **regression+development** (`questions_vnext_tuning.yaml`), 70 questions,
48 answerable, 22 unanswerable. It is the split that exists for decisions. The
holdout stays sealed.

Analysis is **paired**: the same questions in both branches, differences computed
per question, and every question that changes verdict named. Two aggregate rates
over 48 questions have little power; the paired differences have more, and they
say *where* the change is, which is what belongs in the README.

- **`keyword+company` matches or beats `hybrid+company` on correctness, with no
  rise in false refusal and no fall in refusal on unanswerable questions** →
  ordering does not buy answers either. The README describes a lexical system
  with a dense component that was measured and dropped, and the ablation's 0.000
  stops being a retrieval-only finding.

- **`hybrid+company` leads on correctness by more than the paired difference's
  interval** → ordering does produce better answers, for a reason not currently
  measured anywhere. That justifies the dense half on evidence rather than on
  convention, and the README says which questions it wins and why.

- **The paired difference's interval spans zero** → the two are
  indistinguishable at this sample size. That is the result, it gets published as
  the result, and it is not read as support for whichever number happens to be
  higher. In this case the judge's 97.2% self-agreement is the binding
  constraint, and an independent judge over a sample is the next measurement,
  not a rerun of this one.

A guardrail veto overrides the correctness verdict: a branch that raises false
refusal or lowers refusal on unanswerable questions does not win on correctness
alone.

## What this costs

70 questions × 3 runs × 2 branches, generated and judged: roughly 10–12 € at the
rates the earlier runs were measured under. `eval/cache.json` is copied first.
The cache key includes the excerpt ids, so a branch returning different excerpts
pays for them and a branch returning identical ones reuses an answer that would
have been identical anyway.
