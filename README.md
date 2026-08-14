# SEC Filings RAG — retrieval with a measured refusal rate

**Cristina Crespo Barreda** · data analytics, data science, ML engineering

Hybrid retrieval over 20 SEC 10-K filings (~5,000 pages), with citations
verified in code and an evaluation harness that measures whether the system
invents answers it cannot support.

> Work in progress. See `docs/` for the specification.

## Why this is not another RAG chatbot

Anyone can wire a retriever to a language model and get fluent answers. The
question no demo answers is whether those answers are true.

This project measures that. Fifty hand-labeled questions, fifteen of which have
no answer in the corpus and five of which are written to bait a hallucination,
scored on retrieval recall, groundedness, and refusal behavior — with a
false-refusal counter-metric, because a system that refuses everything scores
perfectly on refusal and is useless.

## Architecture

```
EDGAR API → HTML parse → section-aware chunking → local embeddings
                                                       ↓
                                        PostgreSQL + pgvector
                                                       ↓
                    hybrid retrieval: cosine + full-text, fused with RRF
                                                       ↓
                              Claude via Vertex AI, citations verified
                                                       ↓
                                     evaluation harness
```

**Embeddings are computed locally.** The corpus and its vectors never leave the
machine; only the generation call crosses the network, and it sits behind a
provider interface that can be swapped for a local model.

## Stack

Python · PostgreSQL + pgvector · sentence-transformers · Claude via Vertex AI ·
Cloud Run · GitHub Actions
