# The same pipeline on the EU AI Act

The 10-K system, pointed at a regulation instead of annual reports. Nothing in
`src/` changes: same chunker, same encoder, same hybrid retrieval and fusion,
same refusal marker, same citation verification. What is new is a parser that
splits Regulation (EU) 2024/1689 by article, and a runner that adjusts at
runtime what is specific to 10-Ks: the prompt line and the rule that name
filings, the fiscal year in excerpt labels, and company detection.

```powershell
docker compose -f portfolio_aiact/docker-compose.yml up -d --wait
$env:DATABASE_URL = "postgresql://secrag:secrag@localhost:5435/secrag_aiact"
python demo/load_demo.py --corpus portfolio_aiact/aiact_corpus.json
python portfolio_aiact/ask.py "What fines apply for non-compliance with the prohibited AI practices?"
```

Or run everything, corpus build included: `portfolio_aiact\run_demo.ps1`.
Its own database on port 5435, so it cannot touch the development stack (5433)
or the 10-K demo (5434).

## Files

| | |
|---|---|
| `build_corpus.py` | EUR-Lex HTML → 113 articles and 13 annexes → `chunk_section` → bge-small vectors → `aiact_corpus.json` |
| `ask.py` | Runs `generate.answer_question` unchanged and writes `results.json` |
| `aiact.html` | The Regulation as published on EUR-Lex, saved from a browser: EUR-Lex returns an empty page to scripts |
| `aiact_corpus.json` | 242 chunks with their vectors, loadable without the embedding step |
| `results.json` | The run the portfolio video shows, with every excerpt that was sent |

## What the run showed

- **Fines for prohibited practices:** answered with citations to Article 99 and
  Article 100, figures quoted exactly, verification clean.
- **A fine imposed on OpenAI:** declined with `INSUFFICIENT_CONTEXT`. The
  Regulation cannot contain it.
- **When the Regulation starts to apply:** declined, wrongly. Article 113, which
  sets the dates, was not in the sixteen excerpts. Retrieval missed it; the
  refusal was the correct response to what the model was shown.

The first version embedded chunks without their article title and missed
Article 99 as well: the paragraph that sets the fines never uses the words
"penalties" or "maximum". Each chunk now opens with `Article N: title`.

**One run, three questions.** This is a demonstration, not a measurement. The
figures in the main README and `docs/evidence.md` are about the 10-K corpus and
none of them transfers here.

Source: Regulation (EU) 2024/1689, © European Union, https://eur-lex.europa.eu.
Reuse authorised under Commission Decision 2011/833/EU.
