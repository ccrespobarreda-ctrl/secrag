# Run it yourself

Three commands, no corpus download, no embedding run, no API key.

```bash
docker compose -f demo/docker-compose.yml up -d
python demo/load_demo.py
python src/search.py "contract manufacturers footwear production"
```

That is retrieval over 295 chunks of real 10-K text, with the vectors that ship
in this repository. To see an answer with its citations verified, add a
provider — `echo` needs no key and returns a fixed refusal, which is enough to
watch the plumbing work end to end:

```bash
LLM_PROVIDER=echo python src/generate.py "What brands does Gap Inc. operate?"
```

`echo` ignores what it is sent and always returns the same refusal, so its text
reads *"No excerpts were provided to this provider"* even though sixteen were.
What it demonstrates is the path: retrieval, prompt assembly, citation parsing
and refusal detection, all exercised without a token.

With a real key in `.env`, the same command answers from those excerpts with
citations, and every cited excerpt is checked in code against what was actually
sent to the model.

Tear it down, volume and all:

```bash
docker compose -f demo/docker-compose.yml down -v
```

---

## What this is, before you draw conclusions from it

**The extract holds the evidence for all 69 answerable benchmark questions.**
That is not a happy accident: `tests/fixture_corpus.json` was built from every
chunk a gold label points at, plus its neighbours, so any question the published
page lists as answered can be asked here and its evidence is present.

**Retrieval will look better here than the published figures.** Finding the right
passage among 295 is easier than among 4,169, and the numbers on the results page
are the second thing, not this. Nothing measured is reported from this database,
and no figure on the page comes from it. If the demo appears to outperform the
benchmark, the demo is the easier problem.

**Ask about anything outside the extract and it should refuse.** Around fifteen
chunks per filing are present, not two hundred. A question whose evidence is not
here has no answer here, and the correct behaviour is `INSUFFICIENT_CONTEXT`
rather than something assembled from whatever arrived. That refusal is the
property the project measures; seeing it is not the demo failing.

**It is an extract, not a redistribution.** The filings belong to the companies
that wrote them. `src/edgar.py` fetches the corpus from EDGAR; this is the
minimum text needed to reproduce a published check and to see the system run.

---

## Two paths, and why the default needs no model

`src/search.py` runs the full hybrid retriever: dense vectors fused with Postgres
full-text search. The vectors are in the repository, but the *query* still has to
be embedded, so the first run downloads `bge-small-en-v1.5`, about 130 MB, from
the Hugging Face hub. It runs on CPU and costs nothing.

The lexical path needs none of that — no model, no download, no vectors:

```bash
python src/search.py "contract manufacturers footwear production" --compare
```

`--compare` prints the semantic, keyword and hybrid results side by side. Which
is worth reading, because on this benchmark the lexical baseline with the same
company filter ties the full system on Recall@16 across all four splits and
leads it on coverage in two. The dense half contributes ordering, not reach.
That was not the expected result, and it is documented in
[../docs/measurement-honesty.md](../docs/measurement-honesty.md).

---

## Why the demo has its own database

The repository root has a `docker-compose.yml` for development. This one is a
separate project, on port 5434, with its own volume, and the two never share a
container.

The reason is on the record. The label fixture was once loaded into a database
that already held the corpus. The loader upserts rather than truncates, so it
succeeded, and the check that followed reported 4,124 chunks instead of 295 and
looked entirely reasonable. It took an afternoon to notice that a three-digit
number had been measured against the wrong corpus.

Someone cloning this repository has no way to suspect that, so `load_demo.py`
refuses to write into a database that already holds chunks unless you pass
`--force`, and the demo stack can be brought up while your own is running.

---

## Rebuilding the extract

Only needed if the gold labels change. It embeds the fixture on CPU and writes
`demo/demo_corpus.json`:

```bash
python tests/fixture.py --build      # refresh the fixture from the warehouse
python demo/build_demo_corpus.py     # embed it
```

Same model, same normalization, passages embedded raw with the query prefix
applied only on the query side — and the same verification `src/embed.py`
applies to the real run, imported rather than restated, so the demo cannot drift
from the corpus it stands in for.
