# Run it yourself

A 295-chunk extract of the corpus with its vectors, its own Postgres, and no
EDGAR download. Retrieval needs no API key at all.

The commands below were executed on Windows before being written here, which is
the only reason to believe them. The bash block is the same sequence; it has not
been run, and says so.

---

## What it looks like

`python src/generate.py "What brands does Gap Inc. operate?"`

```text
question   'What brands does Gap Inc. operate?'
provider   anthropic

------------------------------------------------------------------------------
ANSWER
------------------------------------------------------------------------------

Gap Inc. operates four brands: Old Navy, Gap, Banana Republic, and Athleta [1].
Old Navy is a North American value apparel brand offering on-trend fashion,
founded in 1994 [1]. Gap is the company's namesake brand, founded in 1969,
offering apparel and accessories along with GapKids, babyGap, Gap Maternity,
GapBody, and GapFit collections [2]. Banana Republic, founded in 1978 and
acquired by Gap Inc. in 1983, is described as a "storyteller's brand" offering
high-quality collections [2]. Athleta, founded in 1998 and acquired by Gap Inc.
in 2008, is a premium performance lifestyle brand certified as a benefit
corporation ("B Corp") [2][3].

------------------------------------------------------------------------------
VERIFICATION
------------------------------------------------------------------------------
  refused          False
  excerpts sent    16
  citations        [1, 2, 3]
  cited chunks     [104, 105, 106]

  every citation points at an excerpt that was actually supplied,
  and no figure is stated without one
```

**The verification block is the part worth looking at.** It is not the model
reporting on itself. Before anything is printed, the code checks that every
citation number exists in what was actually sent, that no sentence carrying a
figure lacks one, and that a refusal stands alone rather than decorating an
answer given anyway. Three separate claims, three cited chunks, all of them
supplied.

---

## Running it

### Windows, PowerShell

```powershell
docker compose -f demo/docker-compose.yml up -d
$env:DATABASE_URL = "postgresql://secrag:secrag@localhost:5434/secrag_demo"
python demo/load_demo.py
python src/generate.py "What brands does Gap Inc. operate?"
```

### macOS and Linux

```bash
docker compose -f demo/docker-compose.yml up -d
export DATABASE_URL="postgresql://secrag:secrag@localhost:5434/secrag_demo"
python demo/load_demo.py
python src/generate.py "What brands does Gap Inc. operate?"
```

**`DATABASE_URL` is not optional and is easy to miss.** Without it the script
reads whatever `.env` sets, which on a development machine is a different
warehouse entirely — the defect this project records as finding 17, in
miniature. `demo/load_demo.py` refuses to load on top of a database that already
holds chunks, for the same reason.

**The last line is the only one that costs anything.** It needs
`ANTHROPIC_API_KEY` in the environment and spends roughly two cents.

### Without an API key

```powershell
$env:LLM_PROVIDER = "echo"
python src/generate.py "What brands does Gap Inc. operate?"
```

This exercises the whole path — retrieval, prompt assembly, citation parsing,
refusal detection, citation verification — and spends nothing. It prints
`INSUFFICIENT_CONTEXT`, because `echo` is not a model and reads none of the
sixteen excerpts it was sent. That is the expected output, not a failure. What
it demonstrates is that the machinery around the model runs; what it cannot
demonstrate is an answer.

### Starting over

```powershell
docker compose -f demo/docker-compose.yml down -v
docker compose -f demo/docker-compose.yml up -d
python demo/load_demo.py
```

---

## What this extract is, and what it is not

295 chunks: every chunk a gold label points at, plus the chunk either side.
About 7% of the 4,124-passage corpus.

**Retrieval over it is an easier problem than retrieval over the corpus**, because
almost everything in it is something a question was written about. None of the
figures in [the README](../README.md) or
[`docs/evidence.md`](../docs/evidence.md) comes from here, and none of them can
be reproduced here. This extract exists so the system can be watched running.
The measurements are a separate claim, made over the whole corpus, and
[`docs/reproducing.md`](../docs/reproducing.md) is where those are rebuilt.

## Questions worth trying

```text
"What were Urban Outfitters' total net sales for the fiscal year ended January 31, 2026?"
"In how many countries are YETI products sold?"
"What was Wayfair's revenue in fiscal year 2030?"
```

The second and third have no answer in the filings. The system is expected to
decline both, and the second one is the question that taught this project the
most: Columbia states "115 countries" and the retriever returns it, so the right
number for the wrong company sits in the excerpts waiting to be used. Finding 20
in [`docs/findings.md`](../docs/findings.md) is what happened when it was.
