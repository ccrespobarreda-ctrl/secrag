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

**Seventeen measurement defects were found, and not one of them was in the RAG.** A
benchmark that scored its own labelling method. A baseline denied a capability
the system had. A verifier that could not fail, twice over. Two headline figures
that rested on one borderline record. A page that asserted a figure it had never
measured. Each produced a plausible number, none raised an error, and every one
was found by checking rather than by anything breaking. Those five are the ones
written up in full in [`docs/measurement-honesty.md`](docs/measurement-honesty.md);
the list below holds all eighteen findings — seventeen defects and one control
that held.

That is the transferable part. The corpus is 10-K filings because they are
public, dense with exact figures, and hard in ways that matter; the labelling
rule, the split discipline, the ablations and the checks that fail loudly are not
about SEC filings at all.

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

## What the harness found

These are the results of auditing my own work, and they are the reason this
repository is worth reading. A benchmark you cannot criticise is a benchmark you
have not checked, so the defects are at the top rather than in an appendix.

Note what is not on this list: not one of them is a bug in retrieval or in
generation. Every one is a defect in how those were being measured, and every one
would have gone on producing a reasonable-looking figure indefinitely.

Four causes account for all seventeen. **This table is an index, not an ordering.**
The numbers are identifiers, fixed in the order the findings were found, and they
are cited from outside this file — `tests/fixture.py` names finding 8 and
`docs/measurement-honesty.md` names finding 9 — so they are never reshuffled to
read better. A reference that still resolves and points at the wrong thing is
finding 7 with a different subject.

| Root cause | Findings |
|---|---|
| **The benchmark was built to be passed.** Labels selected for evidence a keyword search could already reach, scored against a baseline denied a capability the system had. | 1, 2 |
| **Guarantees that were not being made.** A flag, an anchor check, a reproducible run, a checksum list, a benchmark gate, a warehouse nobody named: each looked satisfied, none was. | 5, 7, 10, 14, 15, 17 |
| **The unit of measurement was arbitrary.** Recall scored against one chunk where the evidence spans several, on boundaries that cut an argument from its heading. | 8, 9 |
| **The published figure was not the figure measured.** An evaluator, a detector, a results page, a default argument and a fix that never reached the warehouse, each producing a number the data did not support. | 3, 11, 12, 13, 16, 18 |
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
opens with a one-sentence heading and develops over paragraphs. Measured on the
release corpus, and not recomputed since: the numerator was counted there too,
so this is a figure to measure again rather than divide differently.
**243 of 4,169
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

**15 — The gate protecting the benchmark compared the labels against a copy of
themselves.** `ci.yml` states the case for its own existence: a reload or a
re-chunk silently repoints every gold label, no error is raised, and every
Recall@k figure afterwards is measured against text that is not the answer. So
it stands up Postgres, loads a corpus, confirms all 127 labels resolve, and
concludes that a green build means the measurements can be trusted.

The corpus it loads is `tests/fixture_corpus.json`, which `fixture.py --build`
produced by extracting exactly the chunks the labels name. Once built it cannot
disagree with them. **The gate was immune to the one failure it was written to
catch**, and it stayed green for three weeks while the pipeline stopped
producing the corpus every published figure was measured against.

It surfaced by running the instructions under "Reproducing it" from a clean
clone, which nothing had ever done — the one thing continuous integration does
not do, because the filings are not in the repository. The clone built 4,124
chunks where the release had 4,169, and 23 of 127 labels no longer held. Three
searches settled what that meant: every one of the 23 had its anchor elsewhere
in the same document, none was missing, and the text was byte-identical. Only
the indices had moved, because 45 chunks fewer upstream shifts everything after
them.

The repair is in [`docs/relabel-log.md`](docs/relabel-log.md) and the rule was
written before it ran: a label moved only where exactly one chunk of its
document held content identical to the release text. Not the nearest — Q029's
match is chunk 80 while the nearest candidate is 79, and Q001's anchor appears
in five chunks of Urban Outfitters' filing, one of them a table rejected by hand
in August. Across the fixture's 295 chunks, 294 have exactly one identical
counterpart and none has two, so the mapping is injective and the repair is
checkable rather than plausible. The 23 moved, nothing was left ambiguous, and
all 127 labels now resolve with their content verified, which is a stronger
statement than the one made in August.

**That last sentence was wrong, and finding 17 is why.** The release corpus was
never lost: it is in the warehouse this project measures against, all 4,169
chunks with their vectors. The three searches looked at files, at commits and at
195 blobs, and not one of them opened a database connection.
`tests/fixture_corpus.json` is a second copy of 295 of those chunks rather than
the only one, and it stays in the repository regardless, because a project that
holds its own evidence should not depend on a hosted database still being there.

**And the repair described below was for a different corpus.** The 23 labels were
moved to positions correct in the 4,124-chunk corpus a clean clone builds, and
wrong in the one every published figure was measured over. They have been
restored, and `docs/relabel-log.md` stays: it is the repair a reader needs if
they rebuild the corpus from scratch today.

[`tests/fixture_corpus_clone_20260908.json`](tests/fixture_corpus_clone_20260908.json)
is its counterpart — the same 295 positions as they come out of a clean clone.
**61 of the 295 hold different text**, in consecutive runs of three, which is
the shape a fixture takes when it stores each labelled chunk plus the chunk
either side: 23 labels times three positions, less the overlaps where two labels
sit close together. The other 234 are byte-identical, because only the indices
after a lost chunk shift. Two files, one difference, and together they are the
evidence that a gold label is a property of a corpus rather than of a benchmark.

That file was called `fixture_corpus_release_20260817.json` for a day. It was
copied on 8 September from a fixture rebuilt against the clone's corpus, so the
name asserted a provenance the contents did not have — the same defect as
`eval/results/retrieval.json` holding a measurement taken under `rrf_k=60`. A
name is a claim.

**What was done about it.** The corpus is now declared rather than discovered.
[`eval/corpus_expected.yaml`](eval/corpus_expected.yaml) names the nineteen
filings by accession number, which EDGAR never reuses, alongside the chunk count
and the chunker settings that produce it — a count without its inputs would be
finding 10 again. `src/edgar.py --pinned` fetches exactly those and makes no
submissions request at all, because an accession and a document name are the
whole address; the unpinned path still takes the latest filing per ticker and
now says so. `src/pin_corpus.py --verify` compares the live corpus against the
declaration and stops on a filing that changed, a filing that vanished, or a
chunker that no longer matches.

**And what the gate still cannot do.** The corpus is not in the repository, so
the check in continuous integration compares the declaration against
`data/manifest.json` and stops there: it catches a declaration edited without
its source and a manifest regenerated over different filings, and it does not
count the 4,124 chunks. Nothing in a build without a corpus can. The full check
runs wherever the corpus is loaded, with the same command, and both halves say
which one they are rather than leaving a reader to assume the wider claim.

**16 — Every measurement run without an argument used the abandoned labels.**
`config.EVAL_QUESTIONS` points at `eval/questions.yaml`: 88 labels, 31 of them
with no anchor at all and 30 whose anchor matches more than eight chunks —
`'Wayfair'` in 107, `'Etsy'` in 130. It is the pre-canonical file, the one
finding 1 replaced and finding 7 describes as unable to fail. It is also the
default for `--questions` in ten modules, and `make eval-retrieval` and
`make sabotage` pass no `--questions` at all.

So `make all` ends by measuring against labels the project abandoned, and
returns a plausible number. It returned 0.912, which is the figure this README's
own history attributes to the state before canonical relabelling cost seventeen
points. Reproducing a withdrawn figure exactly is the only reason it was caught:
a number nobody recognised would have been believed. Both measurements are kept
in `eval/results/` so the difference can be attributed rather than argued about.

**What this does not mean.** The published figures were not measured this way.
`FINAL_RELEASE_MANIFEST.json` declares
`"benchmark_file": "eval/questions_canonical.yaml"` and the command recorded in
`docs/handoff-final-es.md` passes it explicitly, so the release ran over the 62
canonical labels. The defect is what an unqualified run measures — `make
sabotage`, `first_run.py`, a reader following the README — not what was
published. The correction is worth as much as the finding: a defect written up
as larger than it is ages worse than one measured. And the fact that settled it
had been sitting in the manifest since 18 August, unread, because provenance
lived in a document rather than in the output of the measurement.

**17 — The project measures against one warehouse and the instructions build
another.** `.env` sets `DATABASE_URL` to a hosted Postgres holding 4,169 chunks,
`chunk_id` 1 to 4,169 with no gaps, loaded once in August and never reloaded. It
is where every published figure was measured. "Reproducing it" tells a reader to
run `docker compose up -d`, which creates a container, and the pipeline fills it
with 4,124. Two warehouses, two corpora, and nothing in the repository said so.

**It cost two days.** On 8 September a clean clone was built to test the
instructions for the first time, `DATABASE_URL` was set by hand to the
container, and every command for the next several hours ran against it: the
corpus diagnosis, the repair of 23 gold labels, the corpus declaration written
by `pin_corpus.py --write`, and a retrieval figure of 0.794. All of it correct
for the container and none of it for this project. The searches that concluded
the release corpus was unrecoverable read files, commits and 195 blobs; not one
opened a database connection.

**The first explanation offered here was wrong.** It said the 45-chunk gap came
from `lxml` and `beautifulsoup4` being unpinned. It does not: `data/chunks.json`
written on 14 August and a clean clone's on 8 September, on `lxml` 6.1.3 against
August's version, hold **4,124 chunks with byte-identical text at every
position**. The pipeline is deterministic and the libraries are not the cause.
The real one is finding 18, and pinning those versions would have fixed
nothing.

**What caught it was the gates written the day before.**
`src/pin_corpus.py --verify` reported 4,169 chunks against 4,124 declared, and
`src/verify_labels.py` failed 20 of 62 labels at their repaired positions — both
within a minute of the environment being loaded correctly, and before a single
euro of generation was spent. Neither gate existed on 7 September.

**And re-running the measurement is what makes the release reproducible rather
than merely frozen.** Recall@16 0.735, MRR 0.310, coverage 0.589, and every
figure by question type, identical to the manifest of 17 August to three decimal
places, twenty-three days later on Python 3.14 and torch 2.14. That is in the
table at the top of this page, and it is the claim this project most wanted to
be able to make.

**Not fixed.** The instructions still build the wrong warehouse. Naming which
one the figures come from is not enough: `requirements.txt` has to pin the parse
dependencies, and then a container has to be shown to produce 4,169 chunks. Until
it does, `src/inspect_warehouse.py` says which corpus is on the other end of
`DATABASE_URL` before anything is measured against it.

**18 — A fix that never reached the warehouse is credited with the improvement
it could not have made.** The table below reports `Re-parse and company
detection fix — 0.882 → 0.912, +0.029`. Both halves are in one commit,
`4001782`, and only one of them could have moved anything.

The times settle it. `eval/results/retrieval_postrecarga.json` is 14 August at
18:30 and reports 0.882: the warehouse had just been reloaded. `data/chunks.json`
was written at 19:39 with 4,124 chunks and the corrected section boundaries.
`eval/results/retrieval_tanda2.json` is 22:45 and reports 0.912. The commit is
23:01. **The re-parse output was written to disk after the reload and never
loaded**, so the corpus the 0.912 was measured over — and every figure since —
carries the section boundaries the commit was written to fix. The gain belongs
to the other half, company detection, which lives in `src/retrieve.py` and needs
no reload; the README's own ablation puts that capability at 0.118.

`src/compare_warehouse_to_disk.py` measures what is still uncorrected there:
45 chunks fewer on disk, and **115 of 4,124 shared positions carrying a
different `item_section`** — `Item 3` where the corrected parse says `Item 7`,
`Item 7` where it says `Item 7A`. That is not cosmetic. `item_section` is read
in five places in `src/retrieve.py` and three in `src/search.py`: it drives the
`--section` filter and the provenance label every excerpt carries into the
prompt, so the model has been told the wrong Item for some of what it was shown.

**What does not change.** Recall@16 0.735, MRR 0.310 and coverage 0.589 are
correct for the corpus they were measured over, and reproduce on it exactly.
What changes is what can be claimed about why they rose.

**And then it was measured.** Two things had to be true first, and both were
checked rather than assumed. The corpus in the warehouse was copied out to disk
with `src/dump_warehouse.py`, because 4,169 vectors existed in Postgres and in
no file. Then the parser from commit `2dc9a47` — the one that precedes the fix —
was run over the same nineteen filings, pinned by accession number, in a clean
clone: **4,169 chunks, byte-identical to the dump at every position.** The corpus
behind every published figure is not an artefact that survived. It rebuilds from
immutable filings and committed code.

Measuring it there gave Recall@16 **0.735**, MRR **0.310** and coverage
**0.589**, and every figure by question type, on a different machine, a
different Postgres and embeddings generated that afternoon. `retrieval_rebuilt_prerefactor.json`
holds it.

**So the experiment finding 18 says was never run had in fact been run in two
halves.** The corrected parse produces the 4,124-chunk corpus, and measured
against the labels that belong to it that corpus gives **0.794**
(`retrieval_vnext_regression.json`). Same code, same filings, same questions,
one commit between them:

| Section boundaries | Chunks | Recall@16 | MRR | Coverage |
|---|---:|---:|---:|---:|
| as measured, uncorrected | 4,169 | 0.735 | 0.310 | 0.589 |
| corrected | 4,124 | 0.794 | 0.321 | 0.633 |

Two questions out of 34, with intervals that overlap over most of their width,
so this is a direction and not a result: correcting the boundaries does not make
retrieval measurably better at this sample size. What it does is remove a defect
from the corpus, and the figure moving at all is the evidence that
`item_section` reaches retrieval rather than decorating it.

**The 0.794 is rehabilitated as something other than what this page claimed
yesterday.** It was described as a measurement resting on better evidence, then
withdrawn as a measurement of a different corpus. It is neither: it is the
isolated effect of a parse fix, which is the only reading the numbers support
and the one nobody had produced.

**Still not fixed.** The warehouse holds the uncorrected corpus, and reloading
it would move every published figure — retrieval by the amount above, and
generation and correctness by amounts nobody has measured. That is a new
evaluation version. What has changed is that it is now a decision with numbers
attached rather than an unknown.

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

## Every component, and the evidence for it

Twelve experiments, each with the number it produced and what was done about it.
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
| **Does better ordering produce better answers?** Hybrid against lexical, company filter held, 48 answerable questions × 3 runs, both generated fresh in one session | Correctness 0.927 against 0.889. **Paired difference +0.038, 95% CI [−0.003, +0.094]** | **Indistinguishable at this sample size, and that is the published result.** Decided by [`docs/decision-rule-ordering.md`](docs/decision-rule-ordering.md), written and committed before the run. Reproduce it with `python analyse_ordering.py` |

**The last row is the only one decided in advance**, and the rule it was decided
by is the reason it can be believed. It fixed the criterion — correctness, not
groundedness, because groundedness is conditional on the excerpts that arrived
and so rewards whichever branch risks least — and it fixed the analysis as
paired, on the grounds that two aggregate rates over 48 questions have little
power. The aggregate counts do show hybrid ahead. That is the comparison the
rule declined in advance.

Four questions separate the branches, and three of them were already named in
[`docs/measurement-honesty.md`](docs/measurement-honesty.md) before this
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

`psql` is not a dependency of this project and the instructions above assumed
it: the container already has it, so
`Get-Content sql/schema.sql -Raw | docker compose exec -T db psql -U secrag -d secrag`
works with nothing installed. That and everything else the first clean clone
hit is in [`docs/first-run-log.md`](docs/first-run-log.md), which is the
instructions being executed rather than asserted.

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
| `analyse_ordering.py` | the paired analysis the decision rule specified |
| `src/pin_corpus.py` | declares the nineteen filings, and verifies the corpus against them |
| `eval/corpus_expected.yaml` | the declaration itself, gated on every push |
| `first_run.py` | the documented instructions, executed and logged |
| `diagnose_labels.py`, `check_fixture_vs_corpus.py` | what broke in finding 15, and why the gate missed it |
| `relabel_review.py`, `apply_relabel.py` | the repair, reviewable then applied by rule |
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
