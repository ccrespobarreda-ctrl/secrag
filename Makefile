# Every target is listed in .PHONY, and every name in .PHONY is a real target.
# An earlier version drifted from both: four targets were defined twice, so make
# silently used the second definition, and `make sabotage` pointed at
# src/evaluate.py -- the single evaluation module the specification planned,
# which the code split into three.
#
# It drifted twice more, and both were found by reading this file against
# .github/workflows/ci.yml rather than by anything failing:
#
#   `help` was a real target and was not in .PHONY, so the line above was false.
#
#   `test` named four test files by hand while CI globbed tests/test_*.py, so
#   tests/test_harness.py ran in CI and not here. A green `make test` and a
#   green build were checking different things. It uses the same wildcard now,
#   and a new test file is picked up by both or by neither.
#
#   `verify-labels` ran the label check with no arguments while the CI gate runs
#   it with --max-anchor-matches 8 --max-exceptions 4. The looser one passing
#   told you nothing about the gate. Both run the gate now.

.PHONY: help setup schema reset-db db-up download parse verify-parse chunk \
        embed load verify-load verify-labels verify-release search \
        eval-retrieval eval-sweep sabotage eval-generation eval-correctness \
        ordering review results-page test all

# Named once, so `test` cannot fall behind the glob CI uses.
TESTS := $(wildcard tests/test_*.py)

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
	@echo "eval/questions_vnext.yaml labels 127 chunk_ids by number; they"
	@echo "survive a reload only if data/chunks.json is unchanged. This warning"
	@echo "named the old 88-label file until 8 September, so it understated"
	@echo "what a reset destroys."
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
	$(PY) src/verify_labels.py --questions eval/questions_vnext.yaml \
	      --max-anchor-matches 8 --max-exceptions 4

verify-release:          ## the frozen release artifacts, byte for byte
	$(PY) verify_release.py

# ── retrieval ────────────────────────────────────────────────────────
search:                  ## compare the three retrieval paths: make search Q="..."
	$(PY) src/search.py "$(Q)" --compare

# The split is named rather than left to config.EVAL_QUESTIONS, and the output
# is named after what it measures. Both were defects on 8 September.
#
# The default was eval/questions.yaml -- 88 pre-canonical labels -- so an
# unqualified run returned 0.912, a figure this project withdrew. It now points
# at the master benchmark, which is correct and still wrong here: a run over the
# master averages the three splits into one number, and the README reports
# retrieval on the original 50 "and never as a single average across splits, for
# the reason in finding 1". Naming the split is what stops the next change of
# default from mattering.
#
# And eval/results/retrieval.json is not written any more. That file holds a
# measurement from 14 August with rrf_k=60, a constant the project has since
# replaced; it is dated evidence of an earlier configuration, and it was the
# destination of both targets below, so `make all` would have overwritten it.
eval-retrieval:          ## Recall@k and MRR, no language model needed
	$(PY) src/evaluate_retrieval.py \
	      --questions eval/questions_vnext_regression.yaml \
	      --save eval/results/retrieval_regression.json

eval-sweep:              ## which fusion constant is right for this corpus
	$(PY) src/evaluate_retrieval.py --sweep

sabotage:                ## degrade the retriever, confirm the metrics move
	$(PY) src/evaluate_retrieval.py --sabotage \
	      --questions eval/questions_vnext_regression.yaml \
	      --save eval/results/retrieval_regression.json

# ── generation and the harness ───────────────────────────────────────
eval-generation:         ## refusal, false refusal and groundedness
	$(PY) src/evaluate_generation.py --runs 3

eval-correctness:        ## is the answer right, not just present
	$(PY) src/evaluate_correctness.py

review:                  ## read the generation results, case by case
	$(PY) src/review_generation.py

ordering:                ## the paired analysis docs/decision-rule-ordering.md specified
	$(PY) analyse_ordering.py

results-page:            ## build docs/index.html from the evaluation files
	$(PY) src/build_results_page.py \
	  --retrieval eval/results/vnext_baseline_legacy_v2.json \
	  --generation eval/results/vnext_generation_promptv2_judge2.json \
	  --generation eval/results/vnext_holdout_generation.json \
	  --second-look eval/results/block2_hybrid.json \
	  --second-look eval/results/block2_keyword.json \
	  --questions eval/questions_vnext.yaml \
	  --out docs/index.html \
	  --contact "c.crespobarreda@gmail.com"

test:                    ## every tests/test_*.py, the same set CI runs
	@for t in $(TESTS); do echo "-- $$t"; $(PY) $$t || exit 1; done

# `sabotage` rather than `eval-retrieval`: it writes the same file with the
# degradation rows the results page expects, so the page never renders a
# sabotage section built from a run that did not measure one.
all: schema download parse verify-parse chunk embed load verify-load \
     verify-labels sabotage
