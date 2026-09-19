# A RAG system over SEC filings, and the evidence that its numbers are real

**Cristina Crespo Barreda** — ML/AI engineer, RAG and evaluation
· [c.crespobarreda@gmail.com](mailto:c.crespobarreda@gmail.com)
· [LinkedIn](https://www.linkedin.com/in/cristina-crespo-/)

**[See it answering questions →](https://ccrespobarreda-ctrl.github.io/secrag/)**
· **[Run it yourself in three commands →](demo/README.md)**
· **[The 21 findings →](docs/findings.md)**

---

## The problem this is about

Most RAG systems ship with a number attached. Recall, accuracy, a groundedness
score. The number was produced once, by the person who built the system, using a
benchmark the same person wrote.

That number is usually wrong, and not because anyone lied. It is wrong because
benchmarks quietly select for the questions the system already handles, because
a verifier can be written in a way that cannot fail, because a figure gets
quoted from a different corpus than the one it was measured over, and because a
single run of a non-deterministic system is a sample reported as a constant.

None of those raise an error. All of them produce a plausible figure. You find
out when a customer asks the system something and it answers confidently about a
document that does not say it.

**This repository is a working RAG over 19 SEC annual reports, and the machinery
that establishes whether its own numbers can be believed.** I audited my own work
and found twenty ways the measurement was lying to me. Every one is written up.
Not one of them was a bug in retrieval or generation.

## What the system does

Ask a question about nineteen 10-K filings. It retrieves the relevant passages,
answers with a citation behind every figure, verifies in code that each citation
points at something it was actually shown, and declines when the documents do
not support an answer.

```text
SEC EDGAR filings
    │
    ├─ HTML parsing, section-aware chunking (420 tokens, 60 overlap)
    ├─ local embeddings (bge-small-en-v1.5) — nothing leaves the machine
    └─ PostgreSQL + pgvector + full-text search
              │
              ├─ semantic retrieval          ─┐
              ├─ lexical retrieval            ├─ reciprocal rank fusion
              └─ company detection and quota ─┘
                        │
                        └─ top-16 excerpts → answer with per-claim citations,
                           citations verified in code, refusal when short
```

Postgres, pgvector and a local embedding model. No vector-database vendor, no
orchestration framework. The only call that leaves the machine is generation,
and it sits behind an interface that takes a locally served model without
changing anything else.

**Refusal is counted, not judged.** The prompt permits declining with an exact
marker, so a refusal is a fact about the output rather than something a second
model has an opinion about. A model told only to answer from the context will
produce something for a question the context cannot answer, because producing
text is what it does. Given a named way out, declining becomes an available move.

## What it costs to run

| | Median | |
|---|---:|---|
| Question to cited answer | **3.40 s** | 0.21 s retrieval, the rest is the model |
| Cost per query | **~0.02 €** | at the rates when it was measured |
| Input tokens per query | 11,150 | sixteen excerpts and the prompt |
| Output tokens | 132 | |

Cost is dominated by what is sent, not by what is written, at 84 to 1. That makes
the excerpt budget the only real lever, and
[`docs/evidence.md`](docs/evidence.md) records what raising it from 8 to 16
bought and what it cost.

## The numbers

All five rows are measured over the same corpus — nineteen filings, 4,124
passages — and the same 50-question regression split, so they can be read
together.

| | Result | |
|---|---:|---|
| Retrieval Recall@16 | **0.794** | 34 answerable questions, 62 audited labels |
| Answer correctness against a human-written reference | **90.2%** | mean of 3 runs |
| Questions with no answer in the corpus, correctly declined | **100%** | 16 questions × 3 runs |
| Answers invented on those questions | **0** | |
| Claims grounded in a cited passage | 99.1% | 333 of 336 decided; 2 judge failures |

**Every figure says how many runs it averages, because three of the four
headline figures in the first release did not — and two of them moved when
measured again.** A refusal rate of 100% from one run of a system at temperature
above zero is a sample, not a property. That is finding 20, and it is the reason
this table looks the way it does.

**The claim I would put weight on is not in the table.** The equivalent
measurement over the previous corpus, re-run twenty-three days later on Python
3.14 against 3.12, torch 2.14 against 2.2 and transformers 5.x against 4.x:
Recall@16, MRR and coverage identical to three decimal places, and every figure
by question type with them. Reproducibility across a materially different
software stack, demonstrated rather than asserted.

**And the intervals matter more than the point estimates.** Zero inventions out
of sixteen questions is not the same claim as zero out of a thousand: the 95%
interval reaches 11%. A system evaluated for overclaiming should not overclaim
in the act of measuring it. [`docs/evidence.md`](docs/evidence.md) carries the
interval on every figure here.

## Why this is worth your time

If you are putting a language model in front of documents, the risk is not that
it answers badly. It is that it answers confidently about something the document
does not say, and the evaluation you built does not notice.

Three things here transfer to any such project, and none is about SEC filings.

**A benchmark can be built to be passed, and usually is.** Half my questions were
labelled by searching the corpus for the answer string, which selects for
questions a keyword search already handles. Measured: a bare full-text search
scores 0.412 on the questions written first and 0.929 on those added later. The
published figure is the lower one.

**A check that cannot fail looks exactly like a check that passes.** The gate
protecting my benchmark loaded a fixture built by extracting the very chunks the
benchmark names. It was immune to the one failure it was written to catch, and it
stayed green for three weeks while the pipeline quietly stopped producing the
corpus every published figure was measured over.

**A decision rule written after the numbers is a description of the numbers.**
Two experiments here were decided by rules written and committed before the runs
happened. Both returned intervals spanning zero. Both were published as such,
including the one where the raw aggregate favoured the more interesting answer.

## What I would do for you

Build the retrieval system, and build the evidence that says whether it works:
the benchmark, the labelling criterion, the ablations that show which components
earn their place, and the gates that fail loudly in continuous integration when
the corpus drifts underneath them.

Three of the ablations here argue against components this system uses — the
dense retriever buys ordering and no additional reach on this corpus, and a
cross-encoder reranker bought nothing for 1.86 seconds. They are published at the
same size as the ones that argued in favour. That is the part most projects skip,
and it is the part that decides whether the first half can be trusted in front of
a customer.

Available for contract and full-time work. Contact above.

---

## Read further

| | |
|---|---|
| [`docs/findings.md`](docs/findings.md) | All twenty-one findings, in full |
| [`docs/measurement-honesty.md`](docs/measurement-honesty.md) | The five that cost the most, written up at length |
| [`docs/evidence.md`](docs/evidence.md) | Thirteen experiments, every ablation, what each component is worth, and the limitations |
| [`docs/decision-rule-ordering.md`](docs/decision-rule-ordering.md) | A decision rule written before the run it decides |
| [`docs/decision-rule-sections.md`](docs/decision-rule-sections.md) | The second one, with two dated amendments |
| [`demo/README.md`](demo/README.md) | Three commands, no API key, no download |
| [`docs/reproducing.md`](docs/reproducing.md) | The full pipeline, and what it still does not reproduce |
