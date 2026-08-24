# SEC filings RAG — measured retrieval, cited answers, and a system that declines

**Cristina Crespo Barreda** · data analytics, data science, ML engineering
· [c.crespobarreda@gmail.com](mailto:c.crespobarreda@gmail.com)

**[See the results and every question →](https://cristinacrespo.github.io/secrag/)**

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
| `src/derive_split.py` | derives split files from the master benchmark |
| `docs/measurement-honesty.md` | the two measurement problems, in full |
| `eval/questions_vnext.yaml` | 100 questions, 127 audited gold labels |

## Licence

Apache 2.0. The filings are public and fetched from EDGAR by `src/edgar.py`; they
are not redistributed here. The labels are mine, assigned by reading the filings,
and the criterion is stated because a recall figure without its labeling
criterion is uninterpretable.
