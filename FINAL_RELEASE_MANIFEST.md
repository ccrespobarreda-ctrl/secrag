# SECRAG — Final Release Manifest

**Release:** `SECRAG-RRF40-2026-08-17`
**Status:** `FINAL_FROZEN`
**Created:** 2026-08-17T17:42:48.796992+02:00

## Final configuration

- Retrieval pool: **50**
- Final top-k: **16**
- RRF k: **40**
- Embedding model: `BAAI/bge-small-en-v1.5`
- Generation model: `claude-sonnet-5`

## Corpus and benchmark

- Corpus chunks: **4,169**
- Benchmark questions: **50**
- Answerable: **34**
- Unanswerable: **16**
- Canonical gold labels: **62**
- Label validation: **62 resolved / 0 failed**

## Final retrieval

Hybrid + company:

- Recall@16: **0.735**
- MRR: **0.310**
- Coverage: **0.589**

By type:

| Type | Recall | Coverage |
|---|---:|---:|
| Comparative | 0.600 | 0.300 |
| Extractive | 0.632 | 0.588 |
| Multi-chunk | 1.000 | 0.735 |

## Final generation

- Generation runs: **3**
- Responses: **150**
- Unanswerable refusal rate: **100.0%**
- False-refusal rate on answerable responses: **2.9%**
- Refusal-decision flips: **0**
- Automatic hallucination rate: **0.0%**
- Groundedness: **97.9%**
- Supported claims: **319/326**
- Unsupported claims: **7**
- Citation-verifier problem responses: **6**

## Correctness — reconciled run 0

| Verdict | Count |
|---|---:|
| Correct | 31 |
| Partially correct | 2 |
| Incorrect | 0 |
| Refused | 1 |
| Judge error | 0 |

- Fully correct: **91.2%**
- Correct or partially correct: **97.1%**
- Incorrect: **0.0%**

Q022's initial judge call returned an empty response and was retried. Its
reconciled verdict is `PARTIALLY_CORRECT`.

## Interpretation of retrieval recall

`Recall@16 = 0.735` is recall against the **canonical labeled chunks**.

Eight canonical-gold misses — Q007, Q008, Q009, Q014, Q015, Q020,
Q034 and Q035 — were manually inspected and contained explicit alternative
supporting evidence in the retrieved top-16.

Therefore canonical-gold recall must not be interpreted as the percentage of
questions for which useful evidence was available.

## Known limitations

- **Q005:** operational retrieval miss; refusal was appropriate for the supplied context.
- **Q022:** correct revenue amounts but incomplete requested growth-rate information.
- **Q027:** core answer correct, but an ancillary Old Navy claim inverted net openings/closures.
- **Q033:** partial answer caused by missing Wayfair-specific evidence.
- **Q044:** correct refusal decision but strict refusal formatting was violated by mentioning $49.0M.
- Correctness was judged on **run 0**, not separately on all three runs.
- Groundedness was judged by the **same model family** as the generator.

## Final artifacts

| File | Bytes | SHA-256 |
|---|---:|---|
| `src/config.py` | 15,781 | `5FAACC51771D19B437391E1EB1344922094FD243E548BFCEDF108BA659256DAD` |
| `src/retrieve.py` | 18,029 | `13E6ABE14D23641BB48F638532D6D536F99C67962204CF0FC3126B988EB8B850` |
| `src/generate.py` | 12,255 | `FA8513B75C8F1B5BA1BC11147DB0E1FDAC0C1856EB64E26435E321EA962465AC` |
| `src/evaluate_retrieval.py` | 11,794 | `AAE9CB188B532745FC9D0DD0864344273F80EFCC009B503B6F9205B59C6A54D4` |
| `src/evaluate_generation.py` | 20,057 | `F1264B2B55283A8C255B5D4E4523B38A908D5E902A3250B1CAF157E4CD7B0ECE` |
| `src/evaluate_correctness.py` | 11,226 | `A5DF48647CB4EFF4E1847C94886CC23E8E378000D08E8EDB4A686F8E4356DA49` |
| `eval/questions_canonical.yaml` | 27,494 | `8F40D8387DC52A072DEC0F4204D0DAFF2C499F05A42F00B4A027F952A3CA6429` |
| `eval/results/retrieval_final.json` | 1,694 | `2F2080B657E78397A6A5DF481C689F8BED077B9404D074BB4D401264953B83D9` |
| `eval/results/generation_final_rrf40.json` | 333,779 | `015DE847646DE2E25D1BA78144185A144EBE3E844B4CA58AAC1D182FE2545C11` |
| `eval/results/correctness_final_rrf40_run0.json` | 52,898 | `00841A80F85CB6D448C8F6417393DE9B01AE605954396D403E35C7F5E0D40F06` |
| `eval/results/correctness_q022_retry.json` | 2,999 | `7D1FCB7549BD777E5A92B2EED193CEFA6532F4BBA683B22647E1A85E70ACC92D` |
| `eval/results/final_evaluation_rrf40.json` | 3,055 | `822559303C27B4E6F5585B52033D32AED6328293FBACE0FDFC0F6C000B1546DB` |

## Freeze rule

These files and hashes define the final evaluated SECRAG release. Changes to
retrieval configuration, benchmark labels, prompts, generation code or result
files constitute a new evaluation version and must not be reported as this
release.
