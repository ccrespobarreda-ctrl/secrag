# What the harness found

Twenty-one findings from auditing this project's own measurements:
twenty defects and one control that held. Not one of them was a bug in
retrieval or generation. Every one produced a plausible figure and
raised no error.

*Part of [secrag](../README.md) — a RAG system over SEC filings, and the evidence that its numbers are real.*

---

## What the harness found

These are the results of auditing my own work, and they are the reason this
repository is worth reading. A benchmark you cannot criticise is a benchmark you
have not checked, so the defects are at the top rather than in an appendix.

Note what is not on this list: not one of them is a bug in retrieval or in
generation. Every one is a defect in how those were being measured, and every one
would have gone on producing a reasonable-looking figure indefinitely.

Four causes account for all twenty. **This table is an index, not an ordering.**
The numbers are identifiers, fixed in the order the findings were found, and they
are cited from outside this file — `tests/fixture.py` names finding 8 and
`docs/measurement-honesty.md` names finding 9 — so they are never reshuffled to
read better. A reference that still resolves and points at the wrong thing is
finding 7 with a different subject.

| Root cause | Findings |
|---|---|
| **The benchmark was built to be passed.** Labels selected for evidence a keyword search could already reach, scored against a baseline denied a capability the system had. | 1, 2 |
| **Guarantees that were not being made.** A flag, an anchor check, a reproducible run, a checksum list, a benchmark gate, a warehouse nobody named, a fixture that could not disagree: each looked satisfied, none was. | 5, 7, 10, 14, 15, 17, 19, 21 |
| **The unit of measurement was arbitrary.** Recall scored against one chunk where the evidence spans several, on boundaries that cut an argument from its heading. | 8, 9 |
| **The published figure was not the figure measured.** An evaluator, a detector, a results page, a default argument and a fix that never reached the warehouse, each producing a number the data did not support. | 3, 11, 12, 13, 16, 18, 20 |
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
[`docs/measurement-honesty.md`](measurement-honesty.md).

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
[`docs/measurement-honesty.md`](measurement-honesty.md) names it.

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
[`FINAL_RELEASE_MANIFEST_ADDENDUM.md`](../FINAL_RELEASE_MANIFEST_ADDENDUM.md)
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

The repair is in [`docs/relabel-log.md`](relabel-log.md) and the rule was
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

[`tests/fixture_corpus_clone_20260908.json`](../tests/fixture_corpus_clone_20260908.json)
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
[`eval/corpus_expected.yaml`](../eval/corpus_expected.yaml) names the nineteen
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

**Now measured.** The warehouse was reloaded with the corrected corpus on
18 September, into a separate Neon branch so the uncorrected one survives. Both
sides were measured for generation and correctness, three runs each, under a
rule written beforehand. The result is below: a paired difference of +2.0% with
a 95% interval of [+0.0%, +4.9%] — indistinguishable at this sample size. The
corrected corpus was adopted anyway, because the boundaries were wrong.

**19 — Five files have to move together and nothing said so.** The gold labels,
the four derived split files, the fixture and the corpus in the warehouse are
one state in five places. Each gate checks a pair of them. No gate checked the
set, and over two days they came apart three times — once because a `git
checkout` staged for a reload that never happened sat on disk for three hours,
and nothing remembered to undo it.

Those three were the good case: the build went red and said which labels no
longer held, and the list of them named the cause. **The bad case happened once
and went green.** On 8 September the fixture was rebuilt against a warehouse
holding a different corpus. It agreed with the labels perfectly, because
`fixture.py --build` extracts the chunks the labels name and `--check` then
confirms the labels are in it — a file compared against a copy of itself, which
is finding 15 in a second place.

`tests/fixture_corpus.json` now records the SHA-256 of the question file it was
built from, and `--check` fails on a mismatch before it looks at a single label.
That fixes the pair that kept drifting and **it does not fix the green case**:
a fixture built from the right labels against the wrong warehouse still passes.
`src/pin_corpus.py --verify` is what says which corpus is on the other end of
`DATABASE_URL`, and the docstring says so rather than leaving the new check
looking broader than it is.

`src/load.py --truncate` now names the host it is about to empty, with the
password stripped, and how many rows go and how many arrive. On 10 September
`DATABASE_URL` was still pointing at the hosted warehouse in a session opened
for a different clone, and that command was one line away from truncating the
corpus every published figure was measured over. It would have printed the three
warnings it always prints, and not one of them names a database.

**20 — Three of the four headline generation figures were single runs of a
system that varies**

The release reports 100% refusal on unanswerable questions, 0% false refusal and
0% hallucination. Each is the value one run produced.

Measured over three runs of the same corpus, on the same split those figures are
quoted for, they are 95.8%, 2.9% and 4.2%. Every one of those differences is the
same question. Q016 asks *"In how many countries are YETI products sold?"* —
YETI states no number, Columbia states "115 countries", and the retriever returns
Columbia's figure at rank 5: the right number for the wrong company, in the
format the question asked for. Across three runs the system refused it once and
answered it twice. Run 0 was the one that was published.

The 0% hallucination rate is therefore not a miscount. It is a sample from a
distribution, reported as a constant, and the harness printed the reason on every
run it made: *without temperature=0 a single run is a sample, not a constant.*

Finding 11 recorded that two headline figures rested on one borderline record and
on which detector counted it. This is the layer underneath: they also rested on
**which run was looked at**.

Correctness varies too, and by more. On the uncorrected corpus, run 1 scores
85.3% and run 2 scores 91.2% over the same 34 questions — three questions change
verdict between identical calls. Q022 is the clearest case: it scores 1 of 3
correct runs on both corpora of the sections experiment, and not one of its three
runs agrees across them. A single run would have reported that question as a gain
or a loss depending on which run was taken.

The correction is not to re-run until the numbers settle. It is that any figure
from this harness carries how many runs it averages, and that a comparison
between two configurations is judged on all of them —
[`docs/decision-rule-sections-amendment-1.md`](decision-rule-sections-amendment-1.md)
is where that became a rule rather than a preference.

**21 — The field that exists to make two measurements comparable is
platform-dependent**

`provenance.describe()` records `questions_sha256`, the hash of the question file
a figure was measured against. It is the decisive field of that block: two runs
of the same file are comparable by construction, and two runs of different files
can no longer be mistaken for each other. Findings 15 and 16 are both
consequences of it not existing earlier.

It hashes the file as it sits in the working tree. `.gitattributes` stores these
files with LF, Windows checks them out as CRLF, and the same committed blob
therefore yields a different hash depending on the platform that measured it:
`2f180d90…` here, `551a14f3…` for the same content on Linux. Two runs of the
same file on different machines appear to be runs of different files, which is
exactly the confusion the field was added to prevent — inverted.

It surfaced while recovering `eval/questions_vnext_regression.yaml` at
`85bd4381…`, the labels the corrected corpus's retrieval figure was measured
against, after the splits were regenerated on 10 September and overwrote it. A
search through every revision in both clones reported that the file had never
been committed. It had been committed all along. The search compared blob bytes
against a hash taken from a working tree, and the answer only appeared once both
line-ending forms were tried.

`tests/test_line_endings.py` covers the corpus text and does not cover this.

The correction is one line — hash the bytes normalised to LF — and it changes
every hash already published, including the ones inside result files that record
what they were measured against. It was deliberately not made during the sections
experiment, because changing the instrument mid-measurement is the defect
[`docs/decision-rule-sections-amendment-2.md`](decision-rule-sections-amendment-2.md)
was written to avoid. It is recorded here, with the correction named, so that it
is not discovered a third time.


## Does correcting the section boundaries produce better answers?

**No, not measurably at this sample size.** The corrected corpus was adopted
anyway.

Finding 18 established that commit `4001782` fixed the section boundaries on
14 August and that its output never reached the warehouse: every published
figure was measured over the corpus that preceded it, with `Item 3` where the
corrected parse says `Item 7` on 115 of 4,124 shared positions. Correcting a
defect does not have to earn its place with a gain, so what was in question was
never whether to adopt the corrected corpus but what could be claimed for it.

The rule was fixed in [`docs/decision-rule-sections.md`](decision-rule-sections.md)
on 11 September, before the generation figures existed, and amended twice — on
11 September when the baseline showed that refusal varies between identical
runs, and on 18 September before the corrected corpus was loaded. Both
amendments are in `docs/`, dated, and neither edits what preceded it.

### The comparison

Both corpora, the same 50-question regression split, the same question file at
`85bd4381…`, the same code, the same provider, three generation runs each and
correctness judged on all three. The uncorrected corpus was measured first,
because reloading the warehouse is what destroys it; the corrected corpus went
into a separate Neon branch rather than over the top of it.

| | uncorrected | corrected |
|---|---:|---:|
| chunks | 4,169 | 4,124 |
| correctness, mean of 3 runs | 88.2% | 90.2% |
| refusal on unanswerable | 95.8% | 100.0% |
| false refusal | 2.9% | 2.9% |
| refusal decisions changing between runs | 1 of 50 | 0 of 50 |
| `JUDGE_ERROR` | 1 | 0 |

**Paired difference +2.0%, 95% bootstrap interval [+0.0%, +4.9%]**, 10,000
resamples over questions, seed 20260918. Two questions improved, none got
worse, thirty-two did not move. A sign test on those gives p = 0.25.

The interval includes zero, so this is the second of the rule's three outcomes:
correcting the boundaries does not measurably change answers at this sample
size. That is the result, and it is not read as support for the higher figure
merely because the higher figure is the new one and retrieval had already moved
in its favour.

### Why the interval reaching exactly zero is not the good news it looks like

The lower bound is `0.0` and not a negative number, which invites the reading
that the effect is never harmful. It is an artefact of the arithmetic rather
than evidence.

Thirty-two of the 34 paired differences are zero. A bootstrap resample that
happens to draw neither of the two questions that moved has a mean of exactly
zero, and that occurs often enough to sit on the 2.5th percentile. The bound is
determined almost entirely by whether two observations are drawn, not by the
spread of the sample. An interval computed over a sample that is 94% zeros is
not estimating much.

The whole +2.0% is two questions each gaining one run out of three:
(1/3 + 1/3) / 34 = 0.0196.

### The two questions that moved, named

**Q029**, from 2 of 3 runs correct to 3 of 3. It is also one of the three
questions whose gold anchor was excused by hand: its anchor is `'2025'`, which
appears in 143 chunks of the same filing, so the label is satisfied wherever it
points. Half of the measured gain rests on the question with the weakest label
in the set. It is named rather than excluded, because excluding it after seeing
which way it went is the move the rule exists to prevent.

**Q025**, from 0 of 3 runs correct to 1 of 3. `PARTIALLY_CORRECT` in every
uncorrected run and in two of the corrected ones.

**And Q022 moved without moving.** It scores 1 of 3 on both sides and
contributes nothing to the difference, yet not one of its three runs agrees
across the two corpora: `PARTIALLY, PARTIALLY, CORRECT` against `CORRECT,
PARTIALLY, PARTIALLY`. Judged on a single run it would have been a gain or a
loss depending on which run was taken. It is the clearest argument for the
rule's insistence on all three.

### The guardrails, and what they stopped

Nothing. They are reported because a rule whose stop conditions are only
mentioned when they fire is a rule nobody can check.

- No question answered by the uncorrected corpus in all three runs is refused by
  the corrected one in all three. **Q005** is refused on both sides in all six
  runs — a constant of the system, not a behaviour change, and the 2.9% false
  refusal on both sides is that one question.
- No question marked unanswerable in the benchmark was answered. 48 of 48
  refused, three runs, both corpora.

### Q016 stopped oscillating

Amendment 1 excluded Q016 from the correctness comparison, before either side
was measured, because its verdict varied between identical calls: *"In how many
countries are YETI products sold?"*, where YETI states no number and Columbia's
"115 countries" returns at rank 5. On the uncorrected corpus it refused once and
answered twice across three runs. On the corrected corpus it refuses in all
three.

That is outside the comparison by construction and it is the most interesting
thing the experiment produced. The corrected corpus did not answer measurably
better; it answered **more deterministically**, and the system's single
published hallucination came from the question that has stopped varying. Whether
the cause is that the corrected boundaries stop pulling Columbia's figure into
the top excerpts is checkable by reading them, and has not been checked here.

### A judge verdict that was wrong, and left standing

In run 1 of the corrected corpus the judge returned `INCORRECT` for **Q033**
with this reason:

> The generated answer claims **Wayfair's** risk is about expansion into new
> offerings rather than customer acquisition…

The answer it was judging says: *"Yes. Chewy describes the risk that if it fails
to acquire and retain new customers cost-effectively…"*, against a reference
reading *"Yes. Chewy says failure to acquire and retain new customers
cost-effectively could harm growth and profitability."* They agree. The judge
produced a confident, specific, traceable verdict about an answer it did not
read, and it named a different company.

It is not a `JUDGE_ERROR` — the JSON parsed, the verdict was legible, and the
harness counted it. It is left standing in the figures above. Amendment 2 fixes
the treatment of the judge before the corrected corpus is measured, and
reclassifying a single verdict after seeing it is the asymmetry the rule
forbids. Q033 scores 0 of 3 correct runs on both sides, so it contributes
nothing to the paired difference in either direction.

The figure that deserves attention is not this repository's correctness rate. It
is that an LLM judge, in a harness built specifically to catch what the other
metrics miss, produced a wrong verdict with a plausible justification, and only
reading the two answers side by side revealed it.

### What it cost

204 judge calls where the August measurement made 34, plus 300 generation
responses across both corpora, 488 API calls on the corrected side alone and
none served from cache — the cache key includes the excerpt ids and a reloaded
corpus reissues every one of them, so both sides were paid in full.


---

*Part of [secrag](../README.md) — a RAG system over SEC filings, and the evidence that its numbers are real.*
