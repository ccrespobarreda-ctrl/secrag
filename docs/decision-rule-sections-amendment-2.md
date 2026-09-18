# Amendment 2 to the section-boundary decision rule

**Written 18 September 2026, after the uncorrected corpus was measured and
before the corrected one is loaded.** It amends
`docs/decision-rule-sections.md` and `docs/decision-rule-sections-amendment-1.md`
and replaces neither. As with amendment 1, the earlier documents say what was
believed when they were written, and editing them now would produce rules that
appear to have foreseen what they did not.

Everything below is decided while only one side of the comparison exists. The
uncorrected corpus was measured on 11 September — `generation_sections_before.json`
and `correctness_sections_before_r0/r1/r2.json`, 4,169 chunks, three runs. The
corrected corpus has not been loaded. Each decision here would have been
available to argue either way once both sides were in, which is why it is
written now.

## What the seven days since the baseline turned up

The baseline run finished and the project was left for a week. Picking it up
again surfaced three things that the rule as it stood did not cover.

**The judge does not always return a verdict.** Q033 in run 1 of the
uncorrected corpus is `JUDGE_ERROR` — no verdict at all, neither correct,
incorrect nor refused. `src/evaluate_correctness.py` counts it separately and
excludes it from `correct_rate`, so that run's rate has a denominator of 34 and
a numerator drawn from 33 judged questions. With the expected effect at one or
two questions, this is not a rounding detail.

**Correctness varies between runs of the same corpus.** Amendment 1 established
that refusal does. Correctness does too: run 1 reports 85.3% and run 2 reports
91.2% over the same 34 questions and the same corpus, with three questions
changing verdict — Q022 and Q029 from `PARTIALLY_CORRECT` to `CORRECT`, and
Q033 from `JUDGE_ERROR` to `INCORRECT`. The rule already judges all three runs
and takes paired differences, which is the right treatment. This is recorded as
the magnitude of the noise the paired interval has to clear.

**The question file the 0.794 was measured against was not on disk.** The
retrieval figure for the corrected corpus cites
`eval/questions_vnext_regression.yaml` at `85bd4381…`, with labels anchored to
4,124 chunks. The file at that path holds `2f180d90…`, anchored to 4,169: the
five `questions_vnext_*.yaml` files were regenerated on 10 September at 23:13
and the migrated version was overwritten. It was recovered on 18 September from
commit `9c4ae87d1`, hashed to confirm it is that file byte for byte, and
committed as `eval/questions_sections_after.yaml` so that a name is not reused
for two contents a second time.

## The decisions

### 1. A `JUDGE_ERROR` is missing data, not an unfavourable verdict

A question's per-run rate is averaged over the runs that returned a legible
verdict. A question that returns none in all three runs is excluded from the
comparison and named. The count of `JUDGE_ERROR` on each side is reported.

An error of the judge is an observation that did not happen. Imputing a value
to it — counting it as incorrect, or as partial — invents a datum, and the
standard treatment of missing data is to drop it from the denominator and say
how many there were rather than to fill it in.

The alternative, retrying the judge until it returns something legible, was
rejected on grounds of symmetry rather than cost. It would require re-judging
Q033 on the uncorrected side, a measurement already closed, knowing that this
particular question may decide the comparison. Changing the instrument
mid-experiment, on a case already seen, is the asymmetry this project exists to
document.

**The risk this accepts** is that `JUDGE_ERROR` may not be random — a judge
that fails more often on long answers, or on one question type, would bias the
exclusion. One instance cannot tell. Hence the reported counts: if the
corrected side returns five where the uncorrected returned one, that is no
longer noise and has to be read rather than averaged over.

### 2. The corpus pin is rewritten, after the reload, in a commit of its own

`eval/corpus_expected.yaml` currently declares 4,169 chunks and
`pin_corpus.py --verify` passes against the warehouse. Loading the corrected
corpus will make that gate fail. The pin will be rewritten to declare 4,124,
under three conditions:

- **After** the reload and after `verify_labels.py` passes.
  `pin_corpus.py --write` derives its counts from the live database; written
  earlier it would declare the corpus being replaced.
- **In a commit containing no measurement.** Commit `4001782` carried two
  changes and made the attribution of +0.029 Recall@16 unrecoverable without a
  forensic reading of timestamps — finding 18. A commit that both replaces the
  corpus and publishes a figure has that same shape: a reader cannot tell
  whether the pin was updated because the corpus was replaced, or the figures
  kept because the pin was made to agree.
- **Preserving the previous declaration** as
  `eval/corpus_expected_release_20260817.yaml`, named in the addendum. That file
  is currently the only machine-readable statement in the repository that the
  release was measured over 4,169 chunks across nineteen filings identified by
  accession number. Overwriting it would leave that claim in prose alone.

The prohibition in `src/pin_corpus.py` is against repairing a *drifted* corpus
by editing the pin, because a pin derived from whatever happens to be loaded
answers nothing. This is not that. The corpus is being replaced deliberately,
under a rule dated 11 September that commits to adopting the corrected corpus
whatever the figures say. What distinguishes the two is not intent, which is
not auditable, but the order of the dates, which is.

**The risk this accepts** is that automatic drift detection is unavailable
between the reload and the rewrite. The window is short and deliberate.

### 3. Both sides are measured on the same Neon instance, on separate branches

The corrected corpus is loaded into a new branch of the same Neon project
rather than over the top of the uncorrected one, and rather than into a local
Postgres.

Against a local Postgres: it introduces a second variable of the same order of
magnitude as the effect. HNSW is approximate, and its recall depends on
`ef_search` and on how the index was built — this project has already measured
that, in `eval/results/retrieval_ef200.json` and `ef40_check.json`. The lexical
half of the RRF runs through `content_tsv`, which depends on the text search
configuration and the Postgres version. Swapping the engine moves both halves
of the fusion at once, and an effect of one or two questions out of 34 could
not then be attributed. The rule of 11 September requires the same code and the
same provider on both sides; the database is part of that.

Against truncating: a branch preserves the 4,169-chunk corpus at no cost to
comparability, since `src/load.py` drops and rebuilds the indexes on every load
regardless.

**The risk this accepts** is two live databases at once, which is the
configuration of the near-miss of 10 September, when `DATABASE_URL` pointed at
the hosted warehouse in a session opened for a different clone. It is accepted
because it is detectable after the fact and the alternative risk is not:
`provenance.describe()` writes `n_chunks` into every result file, so a
measurement made against the wrong branch carries 4,169 where it should carry
4,124 and is visible on opening the file. Two operating rules follow:
`load-env.ps1` never points at both, and `n_chunks` in `measured_against` is
read before any result is believed.

### 4. If the recovered question file does not resolve against the new corpus

`eval/questions_sections_after.yaml` is anchored to a 4,124-chunk corpus built
on another machine. That its 62 labels resolve against the corpus loaded here
is a hypothesis until `verify_labels.py` says otherwise, and it is checked
before any judge call is paid for.

- **All 62 resolve.** The comparison proceeds, and retrieval's 0.794 and the
  generation figures rest on the same labels and may be cited together.
- **Some do not.** The run stops. The failing labels are read and repaired
  against the loaded corpus by the route `docs/relabel-log.md` records, the
  repaired file is given its own name and hash, and **retrieval is measured
  again on it**. The 0.794 was measured against `85bd4381…` and cannot be
  quoted beside generation figures measured against anything else.

Deciding this now rather than on seeing the failure is the same move as
excluding Q016 before knowing whom it would favour.

## What is expected, and why it is finished anyway

The likeliest outcome is a paired interval spanning zero.

Retrieval moved 0.735 to 0.794, two questions out of 34, with intervals
overlapping over most of their width. Correctness varies by 5.9 points between
runs of the same corpus. The effect being looked for is the size of the noise
already measured around it. The second outcome in the rule of 11 September —
*correcting them does not measurably change answers at this sample size* — is
where this most probably lands, and the corrected corpus is adopted in that
case as in every other, because the boundaries were wrong.

This is written down before the result so that an indistinguishable outcome
cannot later be read as a disappointment that an explanation was found for. The
experiment is finished rather than abandoned because a rule written in advance,
measured on both sides, reporting that it found nothing, is better evidence
about how this repository works than a favourable number would be. It would be
the second of that shape here; `docs/decision-rule-ordering.md` was the first.

## Recorded, not acted on

`provenance.describe()` hashes the question file as it sits in the working
tree. Git stores these files with LF under `.gitattributes`, and Windows checks
them out as CRLF, so the same committed file yields a different
`questions_sha256` depending on the platform it was measured on: `2f180d90…`
here against `551a14f3…` for the same blob. The field that exists to make two
measurements comparable is platform-dependent, and two runs of the same file on
different machines would appear to be runs of different files.

`tests/test_line_endings.py` covers the corpus text and does not cover this.
The correction is one line — hash the bytes normalised to LF — and it would
change every hash already published. It is therefore not made here, in the
middle of a measurement. It is named so that it is not discovered a third time,
and it belongs in the findings.
