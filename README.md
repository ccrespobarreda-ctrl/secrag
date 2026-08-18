# SEC Filings RAG - measured retrieval, grounded answers, and refusal behavior

**Cristina Crespo Barreda** - data analytics, data science, ML engineering

RAG system over SEC 10-K filings with hybrid retrieval, company-aware search,
inline citations, refusal handling, and an evaluation harness covering retrieval,
groundedness, answer correctness, and hallucination behavior.

**Final frozen release:** `SECRAG-RRF40-2026-08-17`

See `FINAL_RELEASE_MANIFEST.md` for the authoritative release definition and
`docs/handoff-final-es.md` for the full technical handoff.

## Final evaluated configuration

- Corpus: **4,169 chunks**
- Embeddings: `BAAI/bge-small-en-v1.5`
- Retrieval candidate pool: **50**
- Final top-k: **16**
- RRF k: **40**
- Generation model: `claude-sonnet-5`
- Generation provider used for final evaluation: **Anthropic**

## Canonical benchmark

The canonical benchmark is:

`eval/questions_canonical.yaml`

It contains:

- **50 questions**
- **34 answerable**
- **16 unanswerable**
- **62 canonical gold labels**

Final label validation:

- **62 resolved**
- **0 without anchor**
- **0 failed**

Every canonical label resolves and every anchor remains present in its chunk.

## Final retrieval results

| Strategy | Recall@16 | MRR | Coverage |
|---|---:|---:|---:|
| Semantic | 0.500 | 0.228 | 0.394 |
| Keyword | 0.412 | 0.159 | 0.303 |
| Hybrid | 0.559 | 0.287 | 0.433 |
| Hybrid + company | **0.735** | **0.310** | **0.589** |

Hybrid + company by question type:

| Type | Recall | Coverage |
|---|---:|---:|
| Comparative | 0.600 | 0.300 |
| Extractive | 0.632 | 0.588 |
| Multi-chunk | **1.000** | 0.735 |

`Recall@16 = 0.735` is recall against the canonical labeled chunks.

Eight questions whose canonical gold chunk was not retrieved were manually
inspected and contained explicit alternative supporting evidence in the
retrieved top-16:

- Q007
- Q008
- Q009
- Q014
- Q015
- Q020
- Q034
- Q035

Canonical-gold recall therefore should not be interpreted as the percentage of
questions for which useful evidence was available.

Q005 was the clear operational retrieval miss identified during manual review.

## Final generation results

The canonical generation evaluation used:

- **50 questions**
- **3 runs**
- **150 responses**
- top-k **16**
- `claude-sonnet-5`

Results:

- Unanswerable refusal rate: **100.0%**
- False-refusal rate on answerable responses: **2.9%**
- Refusal-decision flips across runs: **0**
- Automatic hallucination rate: **0.0%**
- Same-family model-judged groundedness: **97.9%**
- Supported claims: **319 / 326**
- Unsupported claims: **7**
- Groundedness judge failures: **1**
- Citation-verifier problem responses: **6**

Zero refusal-decision flips means the answer-vs-refuse decision was stable
across runs. It does not mean the generated answer content was identical.

## Answer correctness

Correctness was evaluated on **generation run 0**.

Q022's first judge call returned an empty response, so it was retried
separately. Its reconciled verdict is `PARTIALLY_CORRECT`.

| Verdict | Count |
|---|---:|
| Correct | **31** |
| Partially correct | **2** |
| Incorrect | **0** |
| Refused | **1** |
| Judge error | **0** |

- Fully correct: **91.2%**
- Correct or partially correct: **97.1%**
- Incorrect: **0.0%**

Correctness and claim-level groundedness should be interpreted together. For
example, Q027 correctly answered the benchmark question but added an ancillary
store-count statement with an inverted sign.

## Known limitations

- **Q005:** operational retrieval miss. The canonical answer evidence was not
  present in the top-16, and the model appropriately refused.

- **Q022:** the response gave correct segment revenue amounts but did not fully
  provide the requested revenue growth rates and added operating-income growth
  instead.

- **Q027:** the core answer was correct, but an ancillary statement said Old
  Navy North America had net openings when the source showed seven net closures.

- **Q033:** Wayfair-specific customer-acquisition evidence was not retrieved,
  resulting in a partially correct comparative answer.

- **Q044:** the refusal decision was correct in all three runs, but the response
  mentioned a `$49.0M` figure and violated the strict refusal-format rule.

- Correctness was evaluated on run 0 rather than independently on all three
  generation runs.

- Groundedness was judged by the same model family used for generation, so the
  97.9% figure is model-judged groundedness rather than independent external
  validation.

## Architecture

```text
SEC filings
    |
    v
HTML parsing + section-aware chunking
    |
    v
Local sentence-transformer embeddings
    |
    v
PostgreSQL + pgvector + full-text search
    |
    v
Semantic + keyword retrieval
    |
    v
RRF fusion + company-aware retrieval
    |
    v
Top-16 numbered excerpts
    |
    v
Claude generation with citations
    |
    v
Citation verification + refusal checks
    |
    v
Retrieval / groundedness / correctness evaluation
