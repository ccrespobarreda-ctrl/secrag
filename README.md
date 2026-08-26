# SEC filings RAG — measured retrieval, cited answers, and a system that declines

**Cristina Crespo Barreda** · data analytics, data science, ML engineering
· [c.crespobarreda@gmail.com](mailto:c.crespobarreda@gmail.com)

**[See the results and every question →](https://ccrespobarreda-ctrl.github.io/secrag/)**

---

If you put a language model in front of your documents, the risk is not that it
answers badly. It is that it answers confidently when the document does not say
what it claims, and nobody notices until the number is in a report.

This system answers questions about SEC 10-K annual reports, cites the passage
behind every figure, verifies those citations in code, and declines when the
documents do not support an answer. The evaluation measures all three.

## The numbers

Measured over 100 questions, 3 runs each, on 19 filings and 4,169 passages.

| | Result | 95% CI |
|---|---:|---|
| Questions with no answer in the corpus, correctly declined | **31 / 31** | [89.0%, 100%] |
| Answers invented on those questions | **0** | [0%, 11.0%] |
| Answerable questions wrongly refused, retrieval-adjusted | **0 / 69** | [0%, 5.3%] |
| Refusal decision changed between runs | **0 / 100** | — |
| Claims grounded in a cited passage | 97.4% | 680 claims, model-judged |
| Retrieval Recall@16 on the original 50 questions | 0.735 | [0.569, 0.854] |

Ten of the 31 unanswerable questions are written to bait an invention: a fiscal
year the filings do not reach, a business segment that does not exist, an
acquisition that never happened. None produced an answer in any run.

**Why the intervals are there.** Zero inventions out of 31 questions is not the
same claim as zero inventions out of a thousand. The interval says how much the
sample supports, and a system evaluated this way should not overclaim in the act
of measuring overclaiming.

## What was found while building it

These are the results of auditing my own work. They are here rather than buried
because a benchmark you cannot criticise is a benchmark you have not checked.

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

**7 — The verifier that checks the benchmark could not fail.** Every gold label
carries an anchor — a phrase that must still be inside the chunk it points at —
and after each reload all 127 were reported as holding. Nothing checked whether
an anchor identified *one* chunk. `'2025'` matches 148 chunks of the Abercrombie
filing; `'Wayfair'` matches 108 chunks written by Wayfair. **35% of anchors match
five or more chunks and would stay satisfied wherever their label drifted.**
Anchor uniqueness is now a gate in continuous integration, with a threshold that
only ratchets down.

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
decision costs — roughly double the input tokens per query. Convert the token
counts above at current rates; they are measured from the API response rather
than estimated from prompt size.

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

- **Chunk boundaries are a known defect and have not been changed.** Fixing them
  means re-chunking, which reissues every `chunk_id` and invalidates all 127
  labels and every published figure. It is the right next change and it is a
  release of its own, not a patch.

## Reproducing it

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
| `src/audit_anchors.py` | anchor uniqueness audit, with proposed replacements |
| `src/check_neighbours.py` | what arrived when a labelled chunk did not |
| `docs/measurement-honesty.md` | the three measurement problems, in full |
| `eval/questions_vnext.yaml` | 100 questions, 127 audited gold labels |

## Licence

Apache 2.0. The filings are public and fetched from EDGAR by `src/edgar.py`; they
are not redistributed here. The labels are mine, assigned by reading the filings,
and the criterion is stated because a recall figure without its labeling
criterion is uninterpretable.
