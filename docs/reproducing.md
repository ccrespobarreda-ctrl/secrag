# Running it, and reproducing the figures

How the system is built, how to run the whole pipeline, what the
repository holds, and what the instructions still do not reproduce.

*Part of [secrag](../README.md) — a RAG system over SEC filings, and the evidence that its numbers are real.*

---

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
whose contribution is zero. [`docs/measurement-honesty.md`](measurement-honesty.md)
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
[`demo/README.md`](../demo/README.md) says so up front.

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
hit is in [`docs/first-run-log.md`](first-run-log.md), which is the
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
| `find_questions_blob.py`, `extract_questions.py` | the recovery behind finding 21, kept so the claim can be re-tested |
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
| `src/compare_sections.py` | the paired comparison of the two corpora, under a rule written first |
| `docs/decision-rule-sections.md` | the second decision rule, with two dated amendments |


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


---

*Part of [secrag](../README.md) — a RAG system over SEC filings, and the evidence that its numbers are real.*
