# The evidence

Every figure this project publishes, what it was measured over, the
thirteen experiments behind the components, and what the numbers still
cannot support.

*Part of [secrag](../README.md) — a RAG system over SEC filings, and the evidence that its numbers are real.*

---

## The numbers

Measured over 100 questions, 3 runs each, on 19 filings and 4,169 passages —
the corpus this pipeline no longer reproduces, which is finding 15.

| | Result | 95% CI |
|---|---:|---|
| Questions with no answer in the corpus, correctly declined | **31 / 31** | [89.0%, 100%] |
| Answers invented on those questions | **0** | [0%, 11.0%] |
| Answerable questions wrongly refused, retrieval-adjusted | **0 / 69** | [0%, 5.3%] |
| Refusal decision changed between runs | **0 / 100** | — |
| Claims grounded in a cited passage | 97.4% | 680 of 694 decided; 11 absence, 3 judge failures |
| Retrieval Recall@16 on the original 50 questions | 0.735 | [0.569, 0.854] |
| The same measurement, twenty-three days later | 0.735 | [0.569, 0.854] |

**The second row is not a second measurement.** It is the same one, re-run on
9 September: same 34 questions, same 62 canonical labels, same 4,169-chunk
corpus. Recall@16 0.735, MRR 0.310 and coverage 0.589, all three identical to
the manifest of 17 August to three decimal places — on Python 3.14 against 3.12,
torch 2.14 against 2.2, and transformers 5.x against 4.x. Every figure by
question type matches too.

That is the strongest claim in this repository and it did not exist until the
figures were re-run. Finding 6 said the release reproduced seven days later on
the same machine; this is twenty-three days later on a materially different
software stack.

**A figure of 0.794 appeared on the way here and is not published.** It was the
same system measuring a corpus built by a clean clone — 4,124 chunks — with
labels repaired for that corpus. It was two questions higher than 0.735 with
overlapping intervals, and yesterday this section described it as resting on
better evidence. It rested on a different corpus. Finding 17 is how that
happened.

Ten of the 31 unanswerable questions are written to bait an invention: a fiscal
year the filings do not reach, a business segment that does not exist, an
acquisition that never happened. None produced an answer in any run.

**Why the intervals are there.** Zero inventions out of 31 questions is not the
same claim as zero inventions out of a thousand. The interval says how much the
sample supports, and a system evaluated this way should not overclaim in the act
of measuring overclaiming.


## Reading the retrieval numbers

Retrieval is reported on the original 50 questions and never as a single average
across splits, for the reason in finding 1. The three splits were defined on 18
August, before the questions they assign were written and two days before any
score existed — the commit history shows it.

| Question set | n | Recall@16 | Coverage |
|---|---:|---:|---:|
| Original 50, written before the system | 34 | 0.735 | 0.589 |
| Sealed holdout | 21 | 0.952 | 0.833 |
| Added later, labeled by literal match | 14 | 0.929 | 0.857 |

The holdout is sealed but not clean: it was built the same way as the third row,
and its bare-keyword score of 0.810 sits far above the first row's 0.412. What
sealing bought is that no parameter was ever chosen with it in view.

### What each component is worth

| Capability removed | Recall@16 | What it was worth |
|---|---:|---:|
| Nothing — the full system | 0.735 | — |
| The company filter and quota | 0.559 | −0.176 |
| The excerpt budget, 16 down to 1 | 0.147 | −0.588 |
| **The dense retriever entirely** | **0.735** | **0.000** |

Measured on the 34 answerable questions of the original 50. The first two are
degradation runs; the third is a lexical baseline holding the company filter
constant.

**The company filter and the excerpt budget do the work. The embeddings and the
rank fusion contribute ordering — MRR 0.310 against 0.280 — and no additional
coverage.** Two further attempts confirmed it rather than reversing it: rewriting
each comparison into per-company sub-queries moved four gold chunks up and one
down, and a cross-encoder reranker over the same candidates left Recall@16
unchanged, cost 0.012 coverage, and added 1.86s to a 3.40s query.

Three neural components, three negative results, on a corpus of financial filings
dense with exact figures and proper nouns. That is a defensible finding about
this domain, and it is not the finding this project set out to make.

### Where the headline figure came from

Retrieval on this corpus was measured seven times between 14 and 17 August. The
figure fell from 0.882 to 0.735 over that period, and every run is kept so the
drop can be attributed rather than assumed.

| Change | Recall@16 | Effect |
|---|---:|---|
| 14 August, RRF k=60 | 0.882 | starting point |
| `hnsw.ef_search` 40 → 200 | 0.882 | **none, to six decimal places** |
| Re-parse and company detection fix | 0.912 | +0.029 |
| **Canonical re-labelling** | **0.735** | **−0.176** |
| RRF k 60 → 40 | 0.735 | recall unchanged, coverage +0.015 |

**The system did not get worse. The labelling got honest.** The single largest
movement in this project's headline metric was reading the filings again and
marking the passage that actually answers each question, and it cost seventeen
points.

A figure that only ever rises is a figure nobody has audited. This one fell,
once, by a documented amount, for a documented reason.


## Every component, and the evidence for it

Thirteen experiments, each with the number it produced and what was done about it.
Three of them argue against components the system uses, and those are kept in
the table rather than dropped from it.

| Experiment | Result | Decision |
|---|---|---|
| `hnsw.ef_search` 40 → 200 | Identical to six decimal places, twice, seven minutes apart | Fixed at 40 in `sql/schema.sql`. Four thousand vectors is too small an index for it to matter, and an undeclared default is worse than a boring one *(finding 10)* |
| RRF constant, k 60 → 40 | Recall unchanged, coverage +0.015 | Adopted. The sweep is `make eval-sweep`, so the constant is a measurement rather than a convention |
| Re-parse and company-detection fix | 0.882 → 0.912 | Kept. **The re-parse half never reached the warehouse and cannot account for any of it** — finding 18. The gain is company detection, which the ablation values at 0.118 |
| Canonical re-labelling of the original 50 | 0.912 → **0.735** | Published the lower figure. The largest movement in the headline metric was reading the filings again, and it cost 17 points *(finding 1)* |
| Remove the company filter and quota | 0.735 → 0.559 | Kept. Worth −0.176, the largest contribution of any component |
| Excerpt budget, 16 → 1 | 0.735 → 0.147 | `top_k` stays 16. Raising it from 8 doubled input tokens, and that is what the coverage on comparison questions costs |
| Remove the dense retriever entirely, filter held constant | **0.735, unchanged.** Lexical leads on coverage | Kept for ordering only — MRR 0.310 against 0.280 — and the earlier claim that embeddings bought a 32-point gap was withdrawn *(finding 2)* |
| Per-company sub-queries for comparisons | Four gold chunks up, one down | Not adopted. Not distinguishable from noise at this sample size |
| Cross-encoder reranker over the same candidates | Recall@16 unchanged, coverage −0.012, +1.86 s on a 3.40 s query | Not adopted. It cost latency and coverage to buy nothing measurable |
| Ask the groundedness judge the same claims twice | 97.2% self-agreement, against 97.4% groundedness reported | The figure is never quoted alone. The instrument's error is the size of the signal *(finding 4)* |
| Re-measure the zero on 22 fresh unanswerable questions | 3.0% and 1.5%, not zero | Both published, inside the interval already given. The sealed holdout was not re-run to settle it *(finding 13)* |
| Rewrite 24 gold anchors to name their passage | Anchors that identify nothing: 29 → 4, and **not one published figure changed** | Adopted and gated in CI at a threshold that only ratchets down. The unchanged figures are the test that this was verification and not tuning *(finding 7)* |
| **Does better ordering produce better answers?** Hybrid against lexical, company filter held, 48 answerable questions × 3 runs, both generated fresh in one session | Correctness 0.927 against 0.889. **Paired difference +0.038, 95% CI [−0.003, +0.094]** | **Indistinguishable at this sample size, and that is the published result.** Decided by [`docs/decision-rule-ordering.md`](decision-rule-ordering.md), written and committed before the run. Reproduce it with `python analyse_ordering.py` |
| **Does correcting the section boundaries produce better answers?** Both corpora, 50-question regression split, 3 runs each, correctness judged on all three | Correctness 0.882 against 0.902. **Paired difference +2.0%, 95% CI [+0.0%, +4.9%]**, two questions up, none down | **Indistinguishable at this sample size, and the corrected corpus was adopted regardless.** Decided by [`docs/decision-rule-sections.md`](decision-rule-sections.md) and its two amendments, all written before the figures existed. Reproduce it with `python src/compare_sections.py` |

**The last two rows are the only ones decided in advance**, and the rule it was decided
by is the reason it can be believed. It fixed the criterion — correctness, not
groundedness, because groundedness is conditional on the excerpts that arrived
and so rewards whichever branch risks least — and it fixed the analysis as
paired, on the grounds that two aggregate rates over 48 questions have little
power. The aggregate counts do show hybrid ahead. That is the comparison the
rule declined in advance.

Four questions separate the branches, and three of them were already named in
[`docs/measurement-honesty.md`](measurement-honesty.md) before this
analysis existed: Q035 is an empty completion the harness counted as answered
plus a labelling gap, Q081 is both branches missing the gold entirely, and
hybrid's win on Q035 came without retrieving either labelled chunk. A difference
built substantially out of labelling artefacts is not evidence about ordering,
which is the same conclusion the interval reaches independently.

**Three neural components, three negative results**, on a corpus dense with
exact figures and proper nouns. That is a defensible finding about this domain,
and it is not the finding this project set out to make. What the table is really
for is the last column: every component here is present or absent because of a
number, and the numbers that argued against the interesting components were
published at the same size as the ones that argued for them.


## What measures what

The pipeline below is the thing being measured. This is the machinery that
measures it, and it is the part of this repository worth reusing.

```text
eval/questions_vnext.yaml — 100 questions, 127 gold labels, an anchor phrase each
    │
    ├─ derive_split.py ····· legacy 50 · development · sealed holdout
    │                        splits derived from the master file, re-verified in
    │                        CI, so a question cannot drift between them unseen
    │
    └─ verify_labels.py ···· does each anchor still identify ONE chunk?
                             --max-anchor-matches 8  --max-exceptions 4
                             thresholds ratchet down, never up  (findings 7, 8)
    │
    ▼
  THREE MEASUREMENTS
    │
    ├─ evaluate_retrieval.py ···· Recall@16 · MRR · coverage · no model called
    │      └─ --sabotage ········ degrade a component, confirm the metric moves
    │
    ├─ evaluate_generation.py ··· refusal · false refusal · groundedness
    │      └─ 3 runs of the same questions; a decision that changes between
    │         runs is instrument noise, not a result  (0 of 100 changed)
    │
    └─ evaluate_correctness.py ·· right, not merely present and well cited
    │
    ▼
  FOUR CHECKS ON THE MEASUREMENTS THEMSELVES
    │
    ├─ compare_splits.py ······· does a bare keyword search score this split
    │                            suspiciously well?  0.412 vs 0.929  (finding 1)
    ├─ check_neighbours.py ····· when the labelled chunk missed, what arrived?
    │                            11 of 24 were adjacent  (finding 9)
    ├─ report_intervals.py ····· one observation per question, and the interval
    │                            that says how little 31 questions support
    └─ the judge against itself · 97.2% self-agreement, 97.4% groundedness
                                 reported. The error is the size of the signal.
    │
    ▼
  build_results_page.py → docs/index.html
    every number read from a results file at build time, and the page says so
    (finding 12 is the one line that was not)
```

Nothing above calls a language model except `evaluate_generation.py` and
`evaluate_correctness.py`. Retrieval, labelling, the splits and every check cost
nothing to run and need no API key, which is why they can be gated on every push:

```text
.github/workflows/ci.yml — six gates, no model call, no cost
  1  verify_release.py ················ the 9 frozen artifacts, byte for byte
  2  tests/test_*.py ·················· parser, chunking, citations, harness
  3  tests/fixture.py --check ········· can the fixture support every label?
  4  tests/fixture.py --load ·········· 300-chunk extract into a real Postgres
  5  verify_labels.py ················· all 127 resolve, every anchor identifies
  6  derive_split.py --verify ········· splits still match the master benchmark
```

Gate 3 exists because gate 5 used to be skipped whenever the corpus was absent,
which was always: the step printed a notice and the build went green, and the
guarantee this README makes about a green build was not being made. Gate 1 was
added the same way — a checksum list nothing ran, with a false entry in it for
six weeks.


## What a question costs, and how long it takes

Measured over four question types × 3 runs, medians rather than means because a
cold connection makes the first call of each type an outlier.

| | Median | Range |
|---|---:|---:|
| Retrieval — local, no API call | **0.21 s** | 0.14 – 0.46 s |
| Generation — one API call | 3.09 s | 2.37 – 7.85 s |
| **Total, question to cited answer** | **3.40 s** | 2.52 – 8.32 s |

| | Median tokens |
|---|---:|
| Input — the sixteen excerpts and the prompt | **11,150** |
| Output — the answer | 132 |

**Cost is dominated by what is sent, not by what is written**, at a ratio of 84
to 1. That makes `top_k` the only real cost lever: it was raised from 8 to 16 to
lift coverage on comparison and multi-passage questions, and this is what that
decision costs — roughly double the input tokens per query. The holdout run cost
3 € in total, which is about 0.02 € per query at the rates in force when it was
measured. Token counts are read from the API response rather than estimated from
prompt size, so they can be reconverted at any later rate.

**Declining is cheaper than answering.** An unanswerable question consumes 10,270
input and 75 output tokens; a multi-passage answer, 10,952 and 577.

Retrieval never leaves the machine and never costs anything. Only the generation
call does, which is also the half that can be pointed at a locally served model.


## Known limitations

- **Q064** is the one answerable question in the sealed set the system declined.
  The evidence exists in the filings; retrieval did not surface it, and a simpler
  lexical baseline does. The refusal was correct, the retrieval failure was not.
- Groundedness is judged by the same model family that wrote the answers. It is
  not independent external validation, and the self-agreement figure above is the
  reason to treat it as approximate.
- **Comparison questions cannot yet decide anything.** At n=5 on the original
  set, the metric moves in steps of 0.2. No retrieval change will be accepted or
  rejected against it until that type is expanded under the corrected labeling
  rule.
- Two question types in the development split sit at 1.000 and are blind: they
  cannot register an improvement or a regression.
- **Whether better ordering produces better answers is measured and
  undecided.** The paired difference is +0.038 with a 95% interval of [−0.003,
  +0.094], so the dense half is not shown to buy answers and not shown not to.
  The rule written before the run names what settles it, and it is not a rerun:
  the judge's 97.2% self-agreement is the binding constraint, so an independent
  judge over a sample is the next measurement.

- **Recall@16 understates operational retrieval.** It is measured against
  canonical labels; 46% of its misses retrieved an adjacent chunk from the same
  document. The figure to compare across systems is 0.735; the figure that
  describes what reaches the model is higher, and answer correctness of 91.2% is
  the closer proxy. Both are published rather than the more flattering one.

- **Four gold anchors still cannot identify their chunk, deliberately.** None
  has an extension carrying a figure from its labelled answer, so a longer anchor
  would buy position at the cost of content. Q029's chunk 55 is the clearest
  case: its only `'2025'` sits inside the filing's page footer, so no window
  around it says anything about the chunk. Each is named in the question file
  with its reason, and records the anchor text it forgives, so an anchor
  rewritten later loses its pardon rather than inheriting one nobody reviewed.
  The continuous-integration threshold stays at 8 and the exception count at 4;
  neither ever rises to make a build pass.

- **The corpus reproduces from the warehouse, not from the pipeline.** Every
  figure above is measured over the 4,169-chunk corpus in the warehouse
  `DATABASE_URL` names, and re-running retrieval against it reproduces the
  published numbers exactly. What does not reproduce it is the documented build:
  `edgar --pinned` fetches the right nineteen filings and the pipeline then
  yields 4,124 chunks, because `requirements.txt` pins no ceiling on `lxml` or
  `beautifulsoup4`. Finding 17. Pinning them, and demonstrating a container that
  produces 4,169, is the work that would close it — and until it is done, a
  reader following the instructions measures their own corpus.

- **`tests/fixture.py --check` still compares the labels against a fixture
  extracted from the labels**, and on its own it cannot fail the way finding 15
  describes. What closes the hole is beside it rather than inside it:
  `src/pin_corpus.py --verify` gates the declared corpus on every push, and the
  full chunk-count check runs where a corpus exists. Making the fixture check
  compare against `data/chunks.json` when that file is present is still worth
  doing, and would make a drifted corpus fail in two places instead of one.

- **Chunk boundaries are a known defect and have not been changed.** Fixing them
  means re-chunking, which reissues every `chunk_id` and invalidates all 127
  labels and every published figure. It is the right next change and it is a
  release of its own, not a patch.


---

*Part of [secrag](../README.md) — a RAG system over SEC filings, and the evidence that its numbers are real.*
