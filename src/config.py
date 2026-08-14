"""
Central configuration.

Every tunable number in the project lives here. When a reviewer asks why chunks
are 800 tokens or why RRF uses k=60, the answer is one file with the reasoning
next to the value.
"""

from __future__ import annotations

import os

# ─────────────────────────────────────────────────────────────────────
# EDGAR
# ─────────────────────────────────────────────────────────────────────
# The SEC requires a declared identity on every request and blocks anonymous
# traffic with a 403. This is not optional.
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "Cristina Crespo Barreda c.crespobarreda@gmail.com"
)

# The SEC publishes a fair-access limit of 10 requests/second. Staying at 5
# leaves headroom and costs nothing at this corpus size.
SEC_MAX_REQUESTS_PER_SECOND = 5

SEC_TICKER_INDEX = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

FORM_TYPE = "10-K"

# ─────────────────────────────────────────────────────────────────────
# The corpus
# ─────────────────────────────────────────────────────────────────────
# US retail and consumer companies, chosen so the corpus extends the DTC
# contribution-margin project rather than sitting beside it unrelated. All are
# listed, all file substantial 10-Ks, and all discuss the same economics:
# inventory, returns, freight, customer acquisition.
# OLPX (Olaplex) and DTC (Solo Brands) did not resolve in the SEC ticker index:
# both are small caps that may have delisted or changed symbol. Replaced with two
# comparable consumer names rather than shrinking the corpus. Which tickers fail
# is itself a data-quality note worth keeping in the README.
COMPANIES = [
    "NKE",   # Nike
    "LULU",  # Lululemon
    "CHWY",  # Chewy
    "W",     # Wayfair
    "ETSY",  # Etsy
    "RVLV",  # Revolve Group
    "YETI",  # Yeti
    "CROX",  # Crocs
    "DECK",  # Deckers Outdoor
    "UAA",   # Under Armour
    "COLM",  # Columbia Sportswear
    "GAP",   # Gap
    "ANF",   # Abercrombie & Fitch
    "URBN",  # Urban Outfitters
    "WRBY",  # Warby Parker
    "FIGS",  # Figs
    "HNST",  # Honest Company
    "LEVI",  # Levi Strauss
    "SKX",   # Skechers
    "PTON",  # Peloton
]

# ─────────────────────────────────────────────────────────────────────
# 10-K structure
# ─────────────────────────────────────────────────────────────────────
# A 10-K has a legally mandated section structure. Carrying the section as
# metadata on every chunk is what allows filtered retrieval ("search only Risk
# Factors") and what separates this from fixed-size chunking that throws the
# document's own organization away.
ITEM_SECTIONS = {
    "Item 1":   "Business",
    "Item 1A":  "Risk Factors",
    "Item 1B":  "Unresolved Staff Comments",
    "Item 2":   "Properties",
    "Item 3":   "Legal Proceedings",
    "Item 5":   "Market for Registrant's Common Equity",
    "Item 7":   "Management's Discussion and Analysis",
    "Item 7A":  "Quantitative and Qualitative Disclosures About Market Risk",
    "Item 8":   "Financial Statements and Supplementary Data",
    "Item 9A":  "Controls and Procedures",
}

# Sections worth indexing. Item 1B is usually the single word "None", and the
# exhibit index is boilerplate; indexing them adds noise to retrieval.
SECTIONS_TO_INDEX = ["Item 1", "Item 1A", "Item 3", "Item 7", "Item 7A", "Item 8"]

# ─────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────
# Dictated by the encoder, not chosen. bge-small-en-v1.5 reports
# max_seq_length = 512 and BERT-family models truncate past it in silence: no
# error, no warning, the tail of every chunk never reaches the vector.
#
# 512 minus [CLS] and [SEP] leaves 510. 420 keeps headroom and still holds a
# complete risk factor, which runs 100-300 words in most filings.
#
# src/chunk.py re-derives this from the loaded model at runtime and refuses to
# run if the budget no longer fits.
CHUNK_TOKENS = 420

# Overlap so a sentence cut by a boundary survives intact in at least one chunk.
CHUNK_OVERLAP_TOKENS = 60

# Below this, a chunk is a heading fragment or a stray table caption with no
# retrievable content.
MIN_CHUNK_TOKENS = 50

# ─────────────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────────────
# Local, on CPU. Two reasons: it is free, and it keeps the corpus and its vectors
# on the machine, so only the generation call ever crosses the network. That is
# the difference between a system a regulated client can use and one they cannot.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
EMBEDDING_BATCH_SIZE = 32

# bge models are trained with an instruction prefix on the query side only.
# Omitting it measurably degrades retrieval, and it is the kind of detail that is
# easy to miss and hard to debug.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# ─────────────────────────────────────────────────────────────────────
# Retrieval
# ─────────────────────────────────────────────────────────────────────
# Each search path returns POOL candidates; RRF fuses them and TOP_K survive
# into the prompt.
RETRIEVAL_POOL = 50

# Raised from 8. Multi-chunk questions need up to five chunks and comparatives
# need evidence from two filings; eight slots shared across nineteen companies
# writing about the same topics produced a measured coverage of 0.25 on
# comparatives and 0.29 on multi-chunk questions.
#
# The cost is more tokens per prompt, which is cents. The benefit is measured by
# src/evaluate_retrieval.py, not assumed.
RETRIEVAL_TOP_K = 16

# Reciprocal Rank Fusion. k=60 is the value from the original paper and the de
# facto convention. It damps the influence of top ranks enough that one search
# path cannot dominate the other.
RRF_K = 60

# ─────────────────────────────────────────────────────────────────────
# Generation
# ─────────────────────────────────────────────────────────────────────
GENERATION_MODEL = os.environ.get("GENERATION_MODEL", "")  # set per provider
MAX_ANSWER_TOKENS = 700

# The exact string the model must emit when the excerpts do not contain the
# answer. It has to be an exact marker, not free text, or refusal cannot be
# measured automatically.
REFUSAL_MARKER = "INSUFFICIENT_CONTEXT"

# ─────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────
RAW_DIR = "data/raw"
PARSED_DIR = "data/parsed"
CIK_CACHE = "data/cik_map.csv"
EVAL_QUESTIONS = "eval/questions.yaml"
EVAL_RESULTS_DIR = "eval/results"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
