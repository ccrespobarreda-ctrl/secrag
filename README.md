# An evaluation harness for document RAG, and the RAG it was built to test

**Cristina Crespo Barreda** · data analytics, data science, ML engineering
· [c.crespobarreda@gmail.com](mailto:c.crespobarreda@gmail.com)

**[See the results and every question →](https://ccrespobarreda-ctrl.github.io/secrag/)**
· **[Run it yourself in three commands →](demo/README.md)**

---

If you put a language model in front of your documents, the risk is not that it
answers badly. It is that it answers confidently when the document does not say
what it claims, and nobody notices until the number is in a report.

The usual answer is to build the system and quote a score. This repository is the
other half: **the machinery that decides whether such a score can be believed**,
and a working RAG over SEC 10-K filings as the thing it is pointed at.

Both halves are here. The system retrieves from 19 annual reports, cites the
passage behind every figure, verifies those citations in code, and declines when
the documents do not support an answer. The harness measures all three, and then
measures itself — which is where the interesting part is.

**Thirteen measurement defects were found, and not one of them was in the RAG.** A
benchmark that scored its own labelling method. A baseline denied a capability
the system had. A verifier that could not fail, twice over. Two headline figures
that rested on one borderline record. A page that asserted a figure it had never
measured. Each produced a plausible number, none raised an error, and every one
was found by checking rather than by anything breaking. Those five are the ones
written up in full in [`docs/measurement-honesty.md`](docs/measurement-honesty.md);
the list below holds all fourteen findings — thirteen defects and one control
that held.

That is the transferable part. The corpus is 10-K filings because they are
public, dense with exact figures, and hard in ways that matter; the labelling
rule, the split discipline, the ablations and the checks that fail loudly are not
about SEC filings at all.

## The numbers

Measured over 100 questions, 3 runs each, on 19 filings and 4,169 passages.

| | Result | 95% CI |
|---|---:|---|
| Questions with no answer in the corpus, correctly declined | **31 / 31** | [89.0%, 100%] |
| Answers invented on those questions | **0** | [0%, 11.0%] |
| Answerable questions wrongly refused, retrieval-adjusted | **0 / 69** | [0%, 5.3%] |
| Refusal decision changed between runs | **0 / 100** | — |
| Claims grounded in a cited passage | 97.4% | 680 of 694 decided; 11 absence, 3 judge failures |
| Retrieval Recall@16 on the original 50 questions | 0.735 | [0.569, 0.854] |

Ten of the 31 unanswerable questions are written to bait an invention: a fiscal
year the filings do not reach, a business segment that does not exist, an
acquisition that never happened. None produced an answer in any run.

**Why the intervals are there.** Zero inventions out of 31 questions is not the
same claim as zero inventions out of a thousand. The interval says how much the
sample supports, and a system evaluated this way should not overclaim in the act
of measuring overclaiming.

## What the harness found

These are the results of auditing my own work, and they are the reason this
repository is worth reading. A benchmark you cannot criticise is a benchmark you
have not checked, so the defects are at the top rather than in an appendix.

Note what is not on this list: not one of them is a bug in retrieval or in
generation. Every one is a defect in how those were being measured, and every one
would have gone on producing a reasonable-looking figure indefinitely.

Four causes account for all thirteen. **This table is an index, not an ordering.**
The numbers are identifiers, fixed in the order the findings were found, and they
are cited from outside this file — `tests/fixture.py` names finding 8 and
`docs/measurement-honesty.md` names finding 9 — so they are never reshuffled to
read better. A reference that still resolves and points at the wrong thing is
finding 7 with a different subject.

| Root cause | Findings |
|---|---|
| **The benchmark was built to be passed.** Labels selected for evidence a keyword search could already reach, scored against a baseline denied a capability the system had. | 1, 2 |
| **Guarantees that were not being made.** A flag, an anchor check, a reproducible run, a checksum list: each looked satisfied, none was. | 5, 7, 10, 14 |
| **The unit of measurement was arbitrary.** Recall scored against one chunk where the evidence spans several, on boundaries that cut an argument from its heading. | 8, 9 |
| **The published figure was not the figure measured.** An evaluator, a detector and a results page, each producing a number the data did not support. | 3, 11, 12, 13 |
| *Not a defect.* The control that held. | 6 |

**1 — The benchmark was inflating its own scores.** Half the questions were
labeled by searching the corpus for the answer string, and questions whose
evidence could not be found that way were dropped. That selects for questions a
plain keyword search already handles. Measured: a bare full-text search scores
0.412 on the questions written first and 0.929 on those added later. The
published retrieval figure is the lower one.

**2 — My baseline was unfair, and fixing it cost me the result.** The first
version of that analysis compared the full system against keyword search without
the company filter, and credited a 32-point gap to retrieval quality. Holding the
filtering constant, the dense retriever and the lexical baseline tie on
Recall@16 across four splits, and the baseline leads on coverage. The embeddings
contribute ordering, not reach. Full account in
[`docs/measurement-honesty.md`](docs/measurement-honesty.md).

**3 — Two parts of the evaluation contradicted each other.** One check counted a
response as a refusal; another flagged that same response for stating figures
inside a refusal. Both were describing a partial answer with its scope declared,
which is the correct response when the evidence was not retrieved. Fixing the
detection moved the apparent false-refusal rate from 2.9% to 0% without touching
the model — the earlier figure was measuring the evaluator.

**4 — The groundedness judge is as noisy as the thing it measures.** Asked the
same claims twice, it agreed with itself 97.2% of the time. The groundedness it
reports is 97.4%. The instrument's error is the size of the signal, so that
figure is never quoted alone.

**5 — `--no-cache` deleted the cache instead of bypassing it.** It started from
an empty dictionary and saved it at the end, overwriting 300 real entries with
no warning. Found by reading the harness while planning an unrelated run.

**6 — The frozen release reproduces exactly.** Seven days later, from a question
file rebuilt by a script, with the evaluation harness modified, on a reloaded
environment: all twelve retrieval figures identical to the manifest of 17 August.

**7 — The verifier that checks the benchmark could not fail, twice over.** Every
gold label carries an anchor — a phrase that must still be inside the chunk it
points at — and after each reload all 127 were reported as holding. Two separate
defects made that guarantee empty.

Nothing checked whether an anchor identified *one* chunk. `'Wayfair'` matched 108
chunks written by Wayfair, and stayed satisfied wherever its label drifted. And
when that check was added, its counting was wrong in two ways at once: `LIKE`
reads the `%` of a percentage as a wildcard, so `'45%'` was never searched for as
written, and the stored text keeps the line breaks of a filing's tables, so a
multi-word anchor read off a printed chunk matched nothing while sitting plainly
inside it. Three successive counts of the same property returned 44, 31 and 29.
**Neither defect ever raised an error. Both produced a plausible number.**

Anchor matches are now counted over whitespace-flattened text and gated in
continuous integration, at a threshold that only ratchets down. Twenty-four
anchors were rewritten to name their passage rather than a word that appears
throughout the filing — `'Wayfair'` became `'of CastleGate and the Wayfair'`,
`'4,966,370'` became `'(Note 10) $ 4,966,370'`. Anchors that cannot identify
their chunk fell from 29 to 4, and **not one published figure changed**, which
is the test that this was verification and not tuning. It reached 4 rather than 5
by reading a chunk: Q029's chunk 83 carried the figure from its own labelled
answer and only needed anchoring on it. The four that remain are named in the
question file with the reason each was left, and that count is gated in
continuous integration and ratchets down like the threshold.

**8 — Chunking cuts risk factors away from their content.** A 10-K risk factor
opens with a one-sentence heading and develops over paragraphs. **243 of 4,169
chunks (5.8%) end just after such a heading, and 230 of those are in Item 1A** —
the section every risk and comparison question asks about. Abercrombie's tariff
risk is labelled on the chunk that ends *"Changes in tariff policy ... could
adversely affect our business."*; the discussion that answers the question is in
the chunk after it.

**9 — Half the retrieval failures were not failures.** Of 24 missed gold chunks,
**11 had an adjacent chunk from the same document retrieved instead**, and
several of those answer the question better than the labelled chunk does. Crocs'
gross profit appears in three chunks because the 60-token overlap duplicates it
across two boundaries — labelling one and scoring the other two as misses
measures an arbitrary choice. The gap between Recall@16 of 0.735 and measured
answer correctness of 91.2% is not a curiosity: it is the size of this artefact,
and it now has three independent measurements behind it.

**10 — Reproducibility rested on a setting nobody had declared.** Vector search
here is approximate: HNSW walks a graph rather than scanning all 4,169 vectors,
and `hnsw.ef_search` decides how wide it walks. It is a database setting, not a
property of the index, so anyone cloning this repository inherited whatever
their pgvector build defaults to and could measure different numbers with
nothing raising an error. It is now fixed at 40 in `sql/schema.sql` — the value
every published figure was measured under. Raising it to 200 was tried on 14
August and changed nothing: two runs seven minutes apart agree to six decimal
places, because four thousand vectors is too small an index for the setting to
matter. **This is the one finding whose fix moves no number: it turns an
assumption into a declaration.**

**11 — Two headline figures rested on one borderline record.** Two result files
holding identical generated text disagreed on one of 210 records, and that single
flip was the whole difference between 65/66 and 66/66 refusal, and between 1/66
and 0/66 hallucination. The cause was a real improvement — refusal detection
moved from a substring test to a rule about whether the limitation *is* the
answer — but publishing the zero without saying which detector produced it was
not. Zero with one detector, one with the other, on the same text.

**12 — The page asserted a figure it had never measured.** Every number on the
results page is read from the results files at build time, and the page says so.
One note under a table was not: it claimed recall 1.000 and coverage 0.350 on
comparatives, and neither figure exists in any results file. It sat four lines
below a comment calling that exact defect the failure this project measures. It
is computed now.

**13 — A second measurement of the zero did not return zero.** Asked again later,
on a different set of 22 unanswerable questions and generated fresh, the
hallucination rate was 3.0% and 1.5% depending on the retriever — inside the
published interval of [0%, 11.0%], and not zero. Both are reported. The sealed
holdout is not re-run to settle it: a second execution prompted by a first result
that was not liked destroys the only property a holdout has. The question that
moves the figure is the same one every time, and
[`docs/measurement-honesty.md`](docs/measurement-honesty.md) names it.

**14 — The frozen release could not be checked, and then could not be
reproduced.**
`SHA256SUMS.txt` fixes the bytes of the frozen release. `.gitattributes` stores
text with LF and checks it out however the platform wants, and the hashes were
computed on Windows over CRLF. So a clone on Linux or macOS reproduces every
artifact faithfully and mismatches all sixteen entries, and nothing in
continuous integration was running the comparison — which is why the README's
own entry could be false from 30 August onwards without anything noticing.

The hashes are unchanged. The bytes they describe are recoverable by restoring
CR to each line, and that is what the check does now, on every push. Regenerating
them was the obvious fix and the wrong one: `FINAL_RELEASE_MANIFEST.md` carries
twelve of them in the same form and is itself frozen, so recomputing would have
traded a declarable convention for two published documents disagreeing about one
artifact.

Running it exposed a larger defect underneath, and the first two explanations
were both wrong. Nine of the fourteen artifacts matched; the five that did not
are the retriever and the three harness modules. The obvious reading was that
the harness had simply moved on — findings 3, 7 and 11 are each an edit to one
of those files — so the code should be verified against the commit the release
was cut from rather than against the disk. That tag did not exist: the frozen
release had been identified by nothing but a commit message. Creating it did not
help, because the tagged blobs did not match either.

**The bytes are in no commit, and in no blob.** Three searches, all kept in the
repository so the claim can be re-tested rather than believed:
`verify_release.py` finds them in neither the working tree nor the tag,
`find_release_commit.py` finds them in none of the 42 commits, and
`find_release_blobs.py` hashes all 195 blobs in the object database, orphaned
ones included, and finds them nowhere. They were hashed from a working tree at
17:42 on 17 August and the files were edited before anything was committed.

So five entries in a list whose purpose is verification can never be satisfied,
and are now marked `record`: the published value stays visible and nothing
pretends to check it. What is still true is that those figures were produced by
that code, that every results file is byte-identical to publication, and that
finding 6 reproduced all twelve retrieval figures a week later from a modified
harness — which is the stronger claim anyway. What was false, and implied by
listing these five as release artifacts, is that a reader can check out the
release and reproduce the bytes.
[`FINAL_RELEASE_MANIFEST_ADDENDUM.md`](FINAL_RELEASE_MANIFEST_ADDENDUM.md)
records it beside the frozen document it corrects, which cannot be edited
without breaking the freeze it defines.

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

## How the system works

```text
SEC EDGAR filings
    │
    ├─ HTML parsing, section-aware chunking (420 tokens, 60 overlap)
    ├─ local sentence-transformer embeddings (bge-small-en-v1.5)
    └─ PostgreSQL + pgvector + full-text search
              │
              ├─ semantic retrieval          ─┐
              ├─ lexical retrieval            ├─ reciprocal rank fusion, k=40
              └─ company detection and quota ─┘
                        │
                        └─ top-16 numbered excerpts
                                  │
                                  ├─ generation with per-claim citations
                                  ├─ citation verification in code
                                  └─ refusal when the excerpts fall short
```

Every component in the pipeline has a measured contribution, including the ones
whose contribution is zero. [`docs/measurement-honesty.md`](docs/measurement-honesty.md)
records what each was worth and what it cost.

Embeddings are computed locally. Only the generation call leaves the machine, and
it sits behind a provider interface so it can be pointed at a locally served
model without changing anything else.

**Why refusal is measurable rather than judged.** The prompt permits refusal
explicitly, with an exact marker, so a refusal can be counted instead of
interpreted. A model told only to "answer from the context" will produce
something for a question the context cannot answer, because producing text is
what it does. Given a named way out, declining becomes an available move.

**What the code checks, before any judge is involved.** Every cited excerpt
number exists in what was actually sent. Every sentence carrying a figure has a
citation. A refusal stands alone rather than decorating an answer given anyway.

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
- Whether better ordering produces better answers has not been measured. The
  generation evaluation ran on one retrieval configuration only.

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

- **Chunk boundaries are a known defect and have not been changed.** Fixing them
  means re-chunking, which reissues every `chunk_id` and invalidates all 127
  labels and every published figure. It is the right next change and it is a
  release of its own, not a patch.

## Reproducing it

The full pipeline fetches nineteen filings from EDGAR and embeds four thousand
passages, which takes a while. To watch the system run first, `demo/` holds a
295-chunk extract with its vectors and needs no download and no API key:

```bash
docker compose -f demo/docker-compose.yml up -d
python demo/load_demo.py
LLM_PROVIDER=echo python src/generate.py "What brands does Gap Inc. operate?"
```

Retrieval over that extract is an easier problem than over the corpus, so its
results are not comparable to the figures above and none of them come from it.
[`demo/README.md`](demo/README.md) says so up front.

The whole thing:

```powershell
docker compose up -d                              # Postgres with pgvector
$env:DATABASE_URL = "postgresql://secrag:secrag@localhost:5433/secrag"
psql $env:DATABASE_URL -f sql/schema.sql

python src/edgar.py                               # fetch filings from EDGAR
python src/parse.py; python src/chunk.py; python src/embed.py; python src/load.py

python src/verify_labels.py --questions eval/questions_vnext.yaml
python src/evaluate_retrieval.py --questions eval/questions_vnext_regression.yaml
```

Retrieval costs nothing to run: no model is called. `LLM_PROVIDER=echo` exercises
the whole generation path — prompt building, citation parsing, refusal detection
— without spending a token.

Continuous integration runs the tests, and separately stands up Postgres and
confirms all 127 gold labels still resolve. A label is a claim about the corpus,
and a re-chunk can falsify it silently.

## Repository

| | |
|---|---|
| `src/retrieve.py` | fusion, company detection, per-company quotas |
| `src/generate.py` | prompt, citation verification, refusal detection |
| `src/evaluate_*.py` | retrieval, groundedness, correctness harnesses |
| `src/compare_splits.py` | cross-split comparison and construction-bias diagnostic |
| `src/report_intervals.py` | confidence intervals, one observation per question |
| `src/check_db_settings.py` | the database settings retrieval depends on |
| `src/fix_anchors.py` | two-phase anchor strengthening, reviewed by a person |
| `src/derive_split.py` | derives split files from the master benchmark |
| `src/check_neighbours.py` | what arrived when a labelled chunk did not |
| `verify_release.py` | the frozen release artifacts, gated in CI |
| `find_release_commit.py`, `find_release_blobs.py` | the searches behind finding 14 |
| `docs/measurement-honesty.md` | the five measurement problems, in full |
| `eval/questions_vnext.yaml` | 100 questions, 127 audited gold labels |
| `demo/` | self-contained extract, its own database, no API key |
| `docs/decision-rule-ordering.md` | a decision rule written and committed before the run it decides |

## Licence

Apache 2.0 covers the code. The labels are mine, assigned by reading the
filings, and the criterion is stated because a recall figure without its
labeling criterion is uninterpretable.

**The filings themselves.** They are public 10-K documents filed with the SEC,
and `src/edgar.py` fetches them; the nineteen annual reports are not
redistributed here. Two extracts of filing text are, and this section used to
say they were not:

- `tests/fixture_corpus.json` — every chunk a gold label points at plus the
  chunk either side, about 300 of 4,169, stored whole. It exists because
  continuous integration was skipping the label check whenever the corpus was
  absent, which was always. Without it the green build guarantees nothing.
- `demo/demo_corpus.json` — the 295-chunk extract behind the three-command demo,
  so the system can be watched running without an EDGAR download or an API key.

Both are the minimum needed to reproduce a published check and to run the thing,
which is a different act from republishing nineteen annual reports, and both are
now named rather than left for a reader to find. Neither is used for any figure
in this README.
