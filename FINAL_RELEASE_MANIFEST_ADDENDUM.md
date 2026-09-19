# Addendum to FINAL_RELEASE_MANIFEST.md

**Status of the manifest:** `FINAL_FROZEN`, and correct as published. Its own
hash verifies.

Five things need saying about it that it cannot say itself. Its freeze rule
makes a change to configuration, benchmark labels, prompts, generation code or
result files a new evaluation version, and it is listed in `SHA256SUMS.txt` with
a hash that holds. Editing it would either break that hash or quietly rewrite a
published document. So the corrections live here, beside it, and this file is
not hashed because it is expected to grow.

---

## 1. The refusal and hallucination rates depend on which detector produced them

The manifest reports **Unanswerable refusal rate: 100.0%** and **Automatic
hallucination rate: 0.0%**.

Both figures rest on a single record out of 210. Two result files holding
identical generated text disagreed on that one record, and the flip is the whole
difference between 65/66 and 66/66 refusal, and between 1/66 and 0/66
hallucination. The cause was a real improvement — refusal detection moved from a
substring test to a rule about whether the limitation *is* the answer — but the
zero was published without naming which detector produced it. Zero with one
detector, one with the other, on the same text.

Read those two figures as "zero under the rule-based detector, one under the
substring detector". Finding 11 in the README is the full account.

## 2. The code artifacts are recorded, not reproducible

The manifest's **Final artifacts** table lists twelve files with their SHA-256
hashes. Nine verify today, byte for byte: `src/config.py`,
`eval/questions_canonical.yaml` and every results file. Those are the evidence,
and they are gated in continuous integration by `verify_release.py`.

The other five — `src/retrieve.py`, `src/generate.py` and the three
`src/evaluate_*.py` modules — cannot be verified against anything. They were
hashed at 17:42 on 17 August from a working tree, and edited before that state
was ever committed. Three searches establish it and are kept in the repository
so it can be re-tested:

| | Result |
|---|---|
| `verify_release.py` | matches neither the working tree nor the release tag |
| `find_release_commit.py` | in none of the 42 commits |
| `find_release_blobs.py` | in none of the 195 blobs in the object database, orphaned included |

**What this does and does not mean.** The published figures were produced by
that code, and every results file it wrote is byte-identical to publication. It
does not mean a reader can check out the release and reproduce those bytes, and
listing the five hashes as release artifacts implied they could. They are marked
`record` in `SHA256SUMS.txt`: kept visible, verified by nothing.

The reproducibility claim that does hold is finding 6, and it is the stronger
one: seven days later, from a question file rebuilt by a script, with the
evaluation harness modified, on a reloaded environment, all twelve retrieval
figures came out identical to this manifest. The figures survived the code
changing, which is a better property than the code being pinned.

## 3. This manifest describes the 50-question release, not the current benchmark

The manifest reports 50 benchmark questions, 34 answerable, 62 canonical gold
labels, groundedness 97.9% and a false-refusal rate of 2.9%. The README reports
100 questions, 127 audited labels, groundedness 97.4% and a false-refusal rate
of 0%.

Neither is wrong. They are different evaluation versions, and the freeze rule is
why: the benchmark was relabelled and the refusal detection corrected, which by
the manifest's own definition makes what came after a new version. The 2.9% here
and the 0% there are the same defect measured before and after the fix described
in finding 3.

When comparing the two documents, `Recall@16 = 0.735` is the figure that means
the same thing in both.

## 4. The release figures cannot be audited question by question

`eval/results/retrieval_final.json` reports Recall@16, MRR and coverage in
aggregate and by question type. It has no `per_question` block, because that
block was added afterwards, for a reason its own comment gives: so an aggregate
can be audited rather than trusted. Two things are impossible without it — a
bootstrap interval on coverage, which is a mean of fractions and not a
proportion, and asking whether two strategies with the same recall missed the
same questions.

So `0.735` can be read and not taken apart. The interval published beside it,
`[0.569, 0.854]`, is a Wilson interval on 25 of 34 questions and is reproducible
from the aggregate alone; the coverage figure of `0.589` has no interval for
exactly this reason. Every measurement taken since carries the per-question
records.

**What the manifest did record, and nobody read.** Line 19 of
`FINAL_RELEASE_MANIFEST.json` declares
`"benchmark_file": "eval/questions_canonical.yaml"`. On 8 September an
afternoon went into establishing which question file the published figures were
measured against, and the answer had been in the manifest since 18 August. The
fact existed; it was in a document rather than in the output of the
measurement, so nobody looked. That is why every result file now opens with
`measured_against`.

## 5. The corpus this manifest was measured over is no longer the one the pipeline loads

Every figure in `FINAL_RELEASE_MANIFEST.md` was measured over a 4,169-chunk
corpus carrying the section boundaries that commit `4001782` was written to fix
and never reached the warehouse — finding 18. On 18 September that corpus was
replaced by the corrected one, 4,124 chunks, and `eval/corpus_expected.yaml` now
declares the corrected corpus rather than the one behind these figures.

**The manifest's figures are unaffected and remain correct as published.** They
describe the corpus they were measured over, and that corpus is not lost: it
rebuilds from the nineteen filings pinned by accession number using the parser
of commit `2dc9a47`, byte-identical at every position, and a copy sits in
`data/warehouse_dump_20260910/` with its hashes. Recall@16 0.735, MRR 0.310 and
coverage 0.589 reproduce on it. What changed is which corpus a reader gets by
following the instructions, and the declaration that says so.

**What was measured before replacing it.** Both corpora, the same 50-question
regression split, the same question file at `85bd4381…`, three generation runs
each and correctness judged on all three, under a rule fixed in
`docs/decision-rule-sections.md` on 11 September and amended twice before the
corrected corpus was loaded. Correctness 88.2% against 90.2%, paired difference
+2.0% with a 95% bootstrap interval of [+0.0%, +4.9%]: indistinguishable at this
sample size. Two questions improved, none got worse. The corrected corpus was
adopted regardless, because the boundaries were wrong, and that was written down
before either side was measured rather than decided by the result. The README
carries the full account and `eval/results/sections_comparison.json` the figures.

**The replacement is in commits of its own.** `d7688f3` rewrites the pin and
contains no measurement, for the reason section 2 of this document illustrates
at a different scale: a commit that both replaces a corpus and publishes a figure
makes the order unrecoverable without reading timestamps. The measurements are in
`50b8a91` and the write-up in `b11b04f`.

**The previous declaration is preserved** as
`eval/corpus_expected_release_20260817.yaml`, so the nineteen filings and the
4,169-chunk count behind this manifest stay machine-readable rather than
surviving only in prose. One flaw in it is worth naming rather than editing: its
header reads *"4,169 and 4169 are both correct counts of different corpora"*, an
artefact of `pin_corpus.py --write` interpolating the live chunk count into a
sentence that assumes it differs from 4,169. It did not, when that file was
written. The sentence is empty and the data below it is correct. It is left as
generated, because a preserved declaration edited by hand is no longer the thing
it was preserved to be.

**`SHA256SUMS.txt` is unchanged.** Nothing it lists was touched: the corpus is
not among the frozen artifacts, and the nine that verify still verify.

---

**The release tag.** `SECRAG-RRF40-2026-08-17` points at the commit that
finalised this release. It reproduces the results files and the configuration
exactly. It does not reproduce the five source files at their published hashes,
for the reason in section 2.
