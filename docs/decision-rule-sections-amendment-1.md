# Amendment 1 to the section-boundary decision rule

**Written 11 September 2026, after the baseline run and before the corrected
corpus is measured.** It amends `docs/decision-rule-sections.md` and does not
replace it. That document says what was believed when it was written; editing it
now would produce a rule that appears to have foreseen what it did not.

## The assumption that failed

The rule sets its stop condition by counting new refusals, and justifies putting
the statistical weight on correctness with this:

> Across the 70 questions of the August file, **refusal changes between runs on
> zero of them**, three runs each.

That was true of `vnext_generation_promptv2_judge2.json` and is not true of the
system. The baseline run of 11 September — the uncorrected corpus, the
50-question regression split, three runs — reports:

| | Value | August's figure |
|---|---:|---:|
| `refusal_rate` on unanswerable | 0.958 | 1.000 |
| `false_refusal_rate` | 0.029 | 0.000 |
| `hallucination_rate` | 0.042 | 0.000 |
| refusal decisions changing between runs | 1 of 50 | 0 of 70 |

Every one of those differences is **one question**: Q016.

## What Q016 is

"In how many countries are YETI products sold?" — an `unanswerable_absent`
question. YETI does not state a number. Columbia states "115 countries" and the
retriever returns it at rank 5: the right figure for the wrong company, in the
format the question asks for. The benchmark's best-designed trap.

Across three runs the system **refuses once and answers twice**. Run 0 is the one
that was published.

So the 0% hallucination rate in the README is not a miscount. It is the value
run 0 produced, from a question whose outcome varies between identical calls,
and the harness prints the reason on every run: *without temperature=0 a single
run is a sample, not a constant.* Finding 11 already recorded that two headline
figures rested on one borderline record and on which detector counted it. This
is the layer underneath: they also rested on **which run was looked at**.

## What changes in the rule

**The stop condition no longer counts refusals.** It cannot: the system produces
new refusals on its own. It is restated on consistency.

- A question that the uncorrected corpus answers in **all three** runs and the
  corrected corpus refuses in **all three** is a change. One or two runs out of
  three is the noise now known to exist, and goes in the report rather than the
  brake.
- **Three or more consistent changes of that kind, or one answerable-in-name
  question the corrected corpus answers in all three runs**, stops the release.
- A single consistent change is named and read before publication; the release
  continues.

**Q016 is excluded from the correctness comparison and reported on both sides.**
A question whose verdict varies between identical calls cannot decide between two
corpora: its contribution is a coin toss, and with 34 answerable questions one
toss is 2.9 points. It is excluded here, before the corrected corpus has been
measured, so that the exclusion cannot be chosen once it is known who it would
favour.

It is not dropped. Both runs report its three verdicts, and the README says what
it is: the one question in the regression split where this system is not a
function of its input.

## What does not change

The corrected corpus is still adopted whatever the result. A worse result is
still published as worse. The guardrails still stop the release rather than
sending the corpus back. Correctness still decides, not groundedness.

## What this makes visible beyond the experiment

The published `refusal_rate` of 100%, `false_refusal_rate` of 0% and
`hallucination_rate` of 0% are single-run figures from a system that varies.
Measured over three runs of the same corpus, on the split they are quoted for,
they are 95.8%, 2.9% and 4.2%. That is a defect in what was published, not in
this experiment, and it belongs in the findings rather than in this amendment —
which is where it has gone, as finding 20.
