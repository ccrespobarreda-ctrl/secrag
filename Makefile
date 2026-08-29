# Every target is listed in .PHONY, and every name in .PHONY is a real target.
# An earlier version drifted from both: four targets were defined twice, so make
# silently used the second definition, and `make sabotage` pointed at
# src/evaluate.py -- the single evaluation module the specification planned,
# which the code split into three.

.PHONY: setup schema reset-db db-up download parse verify-parse chunk embed \
        load verify-load verify-labels search eval-retrieval eval-sweep \
        sabotage eval-generation eval-correctness review results-page test all

PY   := python3
PSQL := psql $(DATABASE_URL)

help:                    ## this list
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) \
	  | sed 's/:.*## /\t/' | expand -t24

# ── setup ────────────────────────────────────────────────────────────
setup:                   ## install dependencies
	$(PY) -m pip install -r requirements.txt

db-up:                   ## local Postgres with pgvector, via Docker
	docker compose up -d

schema:                  ## create tables, indexes and the vector extension
	$(PSQL) -f sql/schema.sql

reset-db:                ## DESTRUCTIVE: drop the tables and the chunk_id sequence
ifneq ($(CONFIRM),yes)
	@echo "This drops chunks and documents, and with them the chunk_id sequence."
	@echo "eval/questions.yaml labels 88 chunk_ids by number; they survive a"
	@echo "reload only if data/chunks.json is unchanged."
	@echo
	@echo "    make reset-db CONFIRM=yes"
	@false
else
	$(PSQL) -f sql/reset.sql
endif

# ── corpus ───────────────────────────────────────────────────────────
download:                ## 10-K filings from EDGAR
	$(PY) src/edgar.py --out data/raw

parse:                   ## HTML -> section-aware text
	$(PY) src/parse.py

verify-parse:            ## sanity-check section boundaries
	$(PY) src/verify_parse.py

chunk:                   ## section-aware chunking
	$(PY) src/chunk.py

embed:                   ## local embeddings on CPU
	$(PY) src/embed.py

load:                    ## into Postgres
	$(PY) src/load.py

verify-load:             ## reconcile the warehouse against the files on disk
	$(PY) src/load.py --dry-run

verify-labels:           ## confirm gold chunk_ids still hold their answers
	$(PY) src/verify_labels.py

# ── retrieval ────────────────────────────────────────────────────────
search:                  ## compare the three retrieval paths: make search Q="..."
	$(PY) src/search.py "$(Q)" --compare

eval-retrieval:          ## Recall@k and MRR, no language model needed
	$(PY) src/evaluate_retrieval.py --save eval/results/retrieval.json

eval-sweep:              ## which fusion constant is right for this corpus
	$(PY) src/evaluate_retrieval.py --sweep

sabotage:                ## degrade the retriever, confirm the metrics move
	$(PY) src/evaluate_retrieval.py --sabotage \
	      --save eval/results/retrieval.json

# ── generation and the harness ───────────────────────────────────────
eval-generation:         ## refusal, false refusal and groundedness
	$(PY) src/evaluate_generation.py --runs 3

eval-correctness:        ## is the answer right, not just present
	$(PY) src/evaluate_correctness.py

review:                  ## read the generation results, case by case
	$(PY) src/review_generation.py

results-page:            ## build docs/index.html from the evaluation files
	$(PY) src/build_results_page.py \
	  --retrieval eval/results/vnext_baseline_legacy_v2.json \
	  --generation eval/results/vnext_generation_promptv2_judge2.json \
	  --generation eval/results/vnext_holdout_generation.json \
	  --questions eval/questions_vnext.yaml \
	  --out docs/index.html \
	  --contact "c.crespobarreda@gmail.com"

test:                    ## parser, chunking and citation tests
	$(PY) tests/test_parse.py
	$(PY) tests/test_chunk.py
	$(PY) tests/test_generate.py
	$(PY) tests/test_retrieve.py

# `sabotage` rather than `eval-retrieval`: it writes the same file with the
# degradation rows the results page expects, so the page never renders a
# sabotage section built from a run that did not measure one.
all: schema download parse verify-parse chunk embed load verify-load \
     verify-labels sabotage
