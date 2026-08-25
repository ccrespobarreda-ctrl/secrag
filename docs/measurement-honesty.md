# How these numbers were checked for inflation

Any retrieval system can be handed a benchmark that flatters it, and any
component can be credited with work it did not do. The usual route is not fraud,
it is convenience: you write the test questions after the system exists, keep the
ones whose answers you can locate, and compare your system against a baseline
that is denied one of its advantages. A third failure is quieter still: the tool
that verifies the labels can be satisfied by an anchor so common that it proves
nothing. In each case nothing looks wrong and the score rises.

All three happened here. This document is how each was caught, how large it is,
which figures survive, and what changed as a result.

**Provenance.** Every figure below comes from release `SECRAG-RRF40-2026-08-17`
against a corpus of 4,169 chunks, embeddings `BAAI/bge-small-en-v1.5`, top-16
retrieval, RRF k=40. All retrieval strategies were measured in a single process
against the same index, so no column reflects a different build; the `generated`
timestamp in each results file records when.

## What the metrics mean

**Recall@16** — did *any* labeled passage appear in the top 16? One question, one
outcome.

**Coverage** — what *fraction* of a question's labeled passages appeared? For a
single-passage question the two are identical. They diverge where the answer is
distributed, and that divergence is the point: a comparison of two companies
whose evidence sits in two filings scores a full hit on Recall@16 when only one
arrives, while a model given those excerpts cannot answer.

**MRR** — one over the rank of the first labeled passage. It sees ordering, which
the other two cannot.

**Why 16.** Raised from 8 before this benchmark existed, for a structural reason:
multi-passage questions need up to five passages and comparisons need evidence
from two filings, and eight slots shared across nineteen companies writing about
the same topics produced a measured coverage of 0.25 on comparisons and 0.29 on
multi-passage questions. The cost is a longer prompt, which is cents.

**What n counts.** Every n is *answerable* questions. The benchmark holds 100
questions; 31 have no answer in the corpus, carry no labeled passage and cannot
appear in a retrieval metric. They are not discarded — they are what the refusal
and hallucination figures are measured on. Question ids run to Q105 because five
numbers were never issued; no question was retired.

## The first problem: the benchmark

The original 50 questions were written by reading the filings and labeling the
passage that answered each. The 50 added later were labeled with a tool that
searches the corpus for the answer string directly, and questions whose evidence
could not be located that way were dropped. That step selects for questions a
plain keyword search can already handle.

The test holds the retriever fixed and varies the question set. Plain Postgres
full-text search — no embeddings, no fusion, no company filter — run against the
same index on the same day:

| Question set | n | Recall@16 |
|---|---:|---:|
| Original 50 (legacy) | 34 | **0.412** |
| Sealed holdout | 21 | 0.810 |
| Added later (development) | 14 | **0.929** |

The questions added later are more than twice as findable by literal search as
the ones written first. That is a property of the questions, measured without
reference to any system.

On the development set the effect is total: plain keyword search and the full
system miss **the same single question**, Q081, and retrieve all thirteen others.
An identical score over an identical set means those questions cannot measure
retrieval quality at all.

## The holdout is sealed, not clean

Sealing prevents tuning against a set. It says nothing about how that set was
labeled, and these are independent properties.

What sealing bought here is unusually strong and is checkable in the commit
history: the three splits were defined on 18 August, **before the questions they
assign were written** (added 19 August) and two days before any score existed
(20 August). No parameter was chosen with these questions in view.

What sealing did not buy is clean labeling. The holdout was built the same way as
the development set, and its keyword-only score of 0.810 sits far above the
original set's 0.412. **It is sealed and partially contaminated.** Its 0.952
should be read that way.

## The second problem: an unfair baseline

The first version of this analysis compared the full system against plain keyword
search and credited the 32-point gap to retrieval quality. That comparison was
invalid: the full system applies a company filter and a per-company quota, and
the baseline was denied both. The gap mixed two separate contributions.

Holding the filtering constant — same company detection, same quota, no
embeddings and no fusion:

| Split | n | | Recall@16 | Coverage | MRR |
|---|---:|---|---:|---:|---:|
| legacy | 34 | keyword + company | 0.735 | **0.628** | 0.280 |
| | | hybrid + company | 0.735 | 0.589 | **0.310** |
| development | 14 | keyword + company | 0.929 | 0.857 | 0.571 |
| | | hybrid + company | 0.929 | 0.857 | **0.637** |
| holdout | 21 | keyword + company | **1.000** | **0.857** | 0.564 |
| | | hybrid + company | 0.952 | 0.833 | **0.660** |

**The dense half of the retriever does not add coverage.** Across four splits it
ties or loses on Recall@16, ties or loses on coverage, and wins on MRR every
time. What the embeddings and the fusion contribute is *ordering*, plus a narrow
advantage on multi-passage questions in the original set — 1.000 against 0.900 on
recall, 0.735 against 0.685 on coverage — where evidence is distributed and no
single lexical match captures it.

Two later attempts confirmed this rather than reversing it. Rewriting each
comparison into per-company sub-queries, so that Under Armour's filing is not
searched with the word "Nike" in the query, moved four gold chunks up and one
down. A cross-encoder reranker over the same candidate pool, with the per-company
quota preserved, left Recall@16 unchanged, cost 0.012 coverage, and added 1.86s
to a 3.40s query.

Three neural components, three negative results. A 10-K is dense with exact
figures and proper nouns, which is the terrain lexical search has always owned.
That is a defensible finding about this domain, and it is not the finding this
project set out to make.

**What has not been measured:** whether better ordering produces better answers.
MRR is a proxy. The generation evaluation ran on hybrid+company only, so the
comparison that would settle it — the same questions generated from the lexical
baseline, judged the same way — has not been done. It is the next measurement and
it is not in this release.

## The control, and its limit

Multi-passage questions should resist the labeling shortcut, because their
evidence is spread across several passages and no single literal match captures
it. Between the original set and the holdout, they behave as predicted:

| Type | Original 50 | Sealed holdout | Added later |
|---|---:|---:|---:|
| Multi-passage coverage | 0.735 (n=10) | 0.750 (n=6) | **1.000 (n=4)** |
| Comparison coverage | 0.300 (n=5) | 0.889 (n=9) | 0.667 (n=6) |
| Single-passage coverage | 0.588 (n=19) | 0.833 (n=6) | **1.000 (n=4)** |

0.735 against 0.750, on ten and six questions, is a difference far smaller than
either sample can resolve — consistent, which is the predicted result if the
divergence elsewhere is an artifact of labeling rather than a change in the
system.

**The control does not hold on the third column, and that is worth stating
plainly.** Multi-passage coverage on the development set is 1.000, which it
should not be if these questions genuinely resisted the shortcut. Two
explanations fit and this data cannot separate them: n=4 is too small to show
anything, or the shortcut partially reaches multi-passage questions when each
passage is located by its own literal search. Either way the control rests only
on the legacy-versus-holdout comparison, where n is 10 and 6, and it is weak
evidence on its own.

## What the aggregates hide

Per-question records make two further claims checkable.

On the original 50, the nine questions hybrid+company misses are a strict subset
of the twenty plain keyword search misses. Of those nine, eight were reviewed by
hand for the frozen release and found to have alternative supporting evidence in
the retrieved passages — the labeled passage was absent, another passage carried
the same fact. One, Q005, was a genuine miss. That earlier manual review
reproduces exactly from the per-question data.

On the holdout the pattern reverses once. **Q064 is retrieved by the lexical
baseline and missed by the full system** — the only question where the fusion
loses something the simpler path found. It is also the one question in the sealed
set the system declined to answer.

## The third problem: the labels themselves

The two problems above are about how questions were selected and what they were
compared against. This one is about whether a label points where it claims to,
and it was found by auditing the tool built to check exactly that.

### The verifier could not fail

`verify_labels.py` treats a label as a falsifiable claim: *the answer to Q014 is
in URBN-10-K-2026, chunk 119, and that chunk contains "Deloitte"*. After every
reload it confirms the anchor is still inside the chunk. It reported all 127
labels as holding.

It had no way to confirm the anchor identified that chunk rather than a hundred
others. Counting each anchor against its own document:

| Anchor matches | Count | Share |
|---|---:|---:|
| One chunk — what a label should mean | 40 | 31% |
| Two or three chunks | 39 | 31% |
| Four chunks | 4 | 3% |
| **Five or more — cannot detect drift** | **44** | **35%** |

The worst are not close calls. `'2025'` matches 148 chunks of the Abercrombie
filing. `'Etsy'` matches 132 chunks of Etsy's. `'Wayfair'` matches 108 chunks
written by Wayfair. An anchor like that stays satisfied wherever its label ends
up, which is precisely the drift the check exists to catch.

The middle band is different and mostly benign: chunks carry a 60-token overlap,
so text near a boundary legitimately appears in two or three of them.

**The fix is a gate rather than a note.** `verify_labels.py` now counts anchor
matches, and `--max-anchor-matches` turns the count into a failure. Continuous
integration runs it at 4 — high enough to allow the overlap, low enough to block
anchors that identify nothing. The threshold is a ratchet: it comes down as
anchors are strengthened and never goes up to make a build pass.

### Chunk boundaries cut risk factors from their headings

Section-aware chunking splits on section boundaries but not on the structure
inside a section. A 10-K risk factor opens with a one-sentence heading and
develops over several paragraphs, and a chunk that ends just after the heading
carries the topic without any of its content.

**243 of 4,169 chunks (5.8%) end that way, and 230 of them are in Item 1A** —
the section every risk and comparison question is about.

Abercrombie's tariff risk is the clearest case. Chunk 53 ends on *"Changes in
tariff policy ... could continue to adversely affect our business."* and nothing
else; chunk 54 contains the entire discussion — the IEEPA, the Supreme Court
ruling, the 10% global tariff, retaliatory measures. The label points at the
heading.

### Half of the retrieval "misses" retrieved a neighbour instead

Of 24 missed gold chunks on the original 50 questions, **11 had an adjacent chunk
from the same document retrieved in its place**. Read individually, several of
those neighbours answer the question at least as well as the labelled chunk.

Sometimes better. Q011 asks what Peloton's primary sources of revenue are; the
labelled chunk defines subscription churn, and the chunk retrieved instead is
headed *Components of our Results of Operations — Revenue*. Q014 asks which firm
audited Urban Outfitters; the labelled chunk describes audit procedures, and the
chunk retrieved instead carries the signature.

And sometimes the distinction is not meaningful at all. Crocs' gross profit,
`2,357,055`, appears in three chunks because the overlap duplicates it across two
boundaries. Labelling one of the three and scoring the other two as misses
measures an arbitrary choice.

### What this does and does not change

**No figure is being restated and nothing is being relabelled.** Relabelling to
accommodate what the retriever found is the failure this document exists to
describe, and it would break comparability with the frozen release.

What changes is how the retrieval figure should be read:

> Recall@16 of 0.735 is measured against canonical labels. Of the misses, 46%
> retrieved an adjacent chunk from the same document, and 5.8% of the corpus
> cuts a risk factor from its heading. Operational retrieval — evidence
> sufficient to answer arriving in the excerpts — sits above the canonical
> figure. Measured answer correctness on the same questions is 91.2%.

That gap between 0.735 and 91.2% was visible in the frozen release and treated
as a curiosity. It is not: it is the size of the labelling artefact, and it now
has three independent measurements behind it.

**Anchors are being strengthened**, because that changes nothing measured.
Anchors take no part in recall or coverage; they only decide whether the verifier
can fail. Replacing `'Wayfair'` with a span that appears once improves the
benchmark's future integrity without touching a single published number, which
makes it the rare change with no reason to distrust it.

## The figures that survive

| | Value | 95% CI | n |
|---|---:|---:|---:|
| Recall@16, original 50 | 0.735 | [0.569, 0.854] | 34 |
| Coverage, original 50 | 0.589 | [0.455, 0.719] | 34 |

Recall is a proportion of questions and uses a Wilson interval. Coverage is a
mean of fractions and uses a percentile bootstrap over questions. Both intervals
are wide because both samples are small; that is the finding, not a defect in the
estimate. The lexical baseline reaches 0.628 coverage on the same questions.

These describe the system because they are the only figures measured on questions
written before it existed. Higher numbers are reported per split and never
averaged: an average across three construction methods describes none of them.

## What changed as a result

**Labeling.** New questions are labeled from the filing first and the literal
search second, and questions whose evidence is *not* findable by literal match
are kept rather than dropped — those are the labels that make Recall@16 mean
anything.

**Baselines.** Every comparison holds filtering constant. A baseline denied a
capability the system has measures the capability, not the comparison.

**Verification.** Anchor uniqueness is checked and gated in continuous
integration. A verifier that cannot fail is not a verifier.

**Reporting.** Every figure carries its split, its n and an interval. Saturated
types are marked as blind rather than quoted as strengths.

**Deciding — and a metric that cannot yet decide.** Comparison questions are the
type with room to move, at 0.300 coverage on the original set. But n=5 there
means the metric moves in steps of 0.2: a single question changing outcome is the
smallest observable difference, and nothing finer can be distinguished from
noise. No retrieval change will be accepted or rejected on that figure until the
comparison type is expanded under the corrected labeling rule. Publishing a
decision metric that cannot resolve the decisions made against it would repeat
the error this document describes.

**Re-labeling.** The 14 development questions are not being re-labeled, and
neither are the labels sitting on the wrong side of a chunk boundary. The bias is
now measured, and a measured bias is more useful than a silent re-labeling that
would invalidate the comparison against the frozen release.

**Not yet fixed.** The chunk boundaries themselves. Re-chunking reissues every
`chunk_id` and invalidates all 127 labels and every published figure, so it is
the next release rather than a patch to this one.

## Why publish this

Every retrieval benchmark built this way carries the first bias, most
system-versus-baseline comparisons carry the second, and almost nobody audits the
third — because a verifier that always passes looks exactly like a benchmark in
good health.

The reason to publish anyway is that a recall figure without its labeling
criterion is uninterpretable, a comparison against a handicapped baseline is not
a comparison, and a label nobody can falsify is not evidence. A supplier who
cannot separate their contribution from their benchmark's is not measuring
anything. The 0.735 is smaller than the 0.952, and the honest account of what the
dense retriever adds is narrower than the original claim. They are the numbers
that mean something.

---

**On refusals.** Refusal and hallucination *rates* are measured on the 31
questions the corpus cannot answer, where there is no labeled passage to find and
no labeling shortcut available, so the benchmark bias above does not reach them.
Retrieval failures can still induce a refusal outside that set: Q064 is a
documented case, where the evidence existed, was not retrieved, and the system
declined to answer rather than construct one. That is the intended behaviour, and
it is counted separately from the unanswerable set.
