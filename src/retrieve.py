"""
Retrieval: semantic, keyword, and hybrid fusion.

Three entry points that return the same shape, so the evaluation harness can
score them against each other and quantify what hybrid actually buys.

    search_semantic(...)   pgvector cosine distance
    search_keyword(...)    Postgres full-text search
    search_hybrid(...)     Reciprocal Rank Fusion over both

AND FIRST, OR ONLY AS A FALLBACK

websearch_to_tsquery produces AND: "supplier concentration risk" becomes
'supplier' & 'concentr' & 'risk', and a chunk must contain all three stems.

An earlier version replaced the operator with OR throughout, justified on a
seven-chunk fixture where AND returned one match and OR returned two. Against the
real corpus that was wrong, and visibly so. For "what were total net revenues for
fiscal 2025", OR ranked seven of eight results from a single filing, all about
trousers and franchised stores.

The reason is that ts_rank rewards term frequency, and under OR the terms doing
the work are 'net', 'total', 'fiscal' and 'revenu' — which appear in every 10-K
on every page. The chunk that repeats them most wins, whether or not it answers
anything. OR loses the requirement that the *distinctive* terms be present.

So AND runs first. OR is the fallback, used only when AND is too strict to return
a usable pool, which is the case the fixture was actually demonstrating.

The OR form is built by replacing the operator in Postgres' own parse output:

    replace(websearch_to_tsquery('english', $1)::text, '&', '|')::tsquery

That keeps Postgres responsible for tokenizing and stemming arbitrary input.
Calling to_tsquery directly on a raw question raises SyntaxError the first time
someone types a parenthesis — verified: "what's the CEO's (home) address?!"
throws, while the pattern above returns 'ceo' | 'home' | 'address'.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402


# ─────────────────────────────────────────────────────────────────────
# Company detection
# ─────────────────────────────────────────────────────────────────────
# Nine of the thirty-four labeled questions returned a top-8 dominated by the
# wrong company. The cause is structural rather than a tuning problem: in the
# embedding, the company name is one token among forty and carries no more weight
# than "revenue"; on the lexical side, ts_rank has no IDF, so "Crocs" ranks the
# same as "gross profit" -- a term that appears in all nineteen filings.
#
# Neither path can learn that the company name is a constraint rather than a
# topic. So it is imposed before retrieval instead of hoped for during it.
#
# The aliases are written out rather than derived from the company column,
# because the filings say "NIKE, Inc." and questions say "Nike", and matching on
# the legal name would catch almost nothing.
COMPANY_ALIASES: dict[str, tuple[str, ...]] = {
    "NKE":  ("nike",),
    "LULU": ("lululemon",),
    "CHWY": ("chewy",),
    "W":    ("wayfair",),
    "ETSY": ("etsy",),
    "RVLV": ("revolve",),
    "YETI": ("yeti",),
    "CROX": ("crocs",),
    "DECK": ("deckers", "ugg", "hoka"),
    "UAA":  ("under armour", "under armor"),
    "COLM": ("columbia sportswear", "columbia"),
    "GAP":  ("gap inc", "the gap", "old navy", "banana republic", "athleta"),
    "ANF":  ("abercrombie", "hollister"),
    "URBN": ("urban outfitters", "anthropologie", "free people"),
    "WRBY": ("warby parker", "warby"),
    "FIGS": ("figs",),
    "HNST": ("honest company", "the honest"),
    "LEVI": ("levi strauss", "levi's", "levis", "levi"),
    "PTON": ("peloton",),
}


def detect_companies(question: str) -> list[str]:
    """
    Tickers named in a question, in the order they appear.

    Longest alias first, so "columbia sportswear" is not shadowed by "columbia",
    and word boundaries so "gap" does not match "gaps in coverage".
    """
    import re as _re

    lowered = question.lower()
    found: list[tuple[int, str]] = []

    for ticker, aliases in COMPANY_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            m = _re.search(rf"\b{_re.escape(alias)}\b", lowered)
            if m:
                found.append((m.start(), ticker))
                break

    seen, out = set(), []
    for _, ticker in sorted(found):
        if ticker not in seen:
            seen.add(ticker)
            out.append(ticker)
    return out


@dataclass
class Hit:
    chunk_id: int
    doc_id: str
    ticker: str
    company: str
    fiscal_year: int
    item_section: str | None
    section_title: str | None
    content: str
    score: float
    semantic_rank: int | None = None
    keyword_rank: int | None = None

    def label(self) -> str:
        """Short provenance string for the prompt: (Nike, FY2023, Item 1A)."""
        parts = [self.company, f"FY{self.fiscal_year}"]
        if self.item_section:
            parts.append(self.item_section)
        return "(" + ", ".join(parts) + ")"


# Postgres parses the raw question in both forms; only the boolean operator
# differs.
_AND_TSQUERY = "websearch_to_tsquery('english', %(q)s)"
_OR_TSQUERY = "replace(websearch_to_tsquery('english', %(q)s)::text, '&', '|')::tsquery"

# Below this many AND matches the pool is too thin to rank, and OR is tried
# instead. Chosen so a question whose terms genuinely co-occur never falls back.
KEYWORD_MIN_AND_HITS = 5

_SELECT_FIELDS = """
    c.chunk_id, c.doc_id, d.ticker, d.company, d.fiscal_year,
    c.item_section, c.section_title, c.content
"""


def _section_filter(sections: list[str] | None) -> tuple[str, dict]:
    """Optional restriction to specific 10-K items."""
    if not sections:
        return "", {}
    return " and c.item_section = any(%(sections)s) ", {"sections": sections}


def _ticker_filter(tickers: list[str] | None) -> tuple[str, dict]:
    if not tickers:
        return "", {}
    return " and d.ticker = any(%(tickers)s) ", {"tickers": tickers}


def _filters(sections, tickers) -> tuple[str, dict]:
    sec_sql, sec_p = _section_filter(sections)
    tick_sql, tick_p = _ticker_filter(tickers)
    return sec_sql + tick_sql, {**sec_p, **tick_p}


def search_semantic(cur, query_vector: list[float], top_k: int = C.RETRIEVAL_TOP_K,
                    sections: list[str] | None = None,
                    tickers: list[str] | None = None) -> list[Hit]:
    where, params = _filters(sections, tickers)
    cur.execute(f"""
        select {_SELECT_FIELDS}, 1 - (c.embedding <=> %(qv)s::vector) as score
        from chunks c
        join documents d using (doc_id)
        where c.embedding is not null {where}
        order by c.embedding <=> %(qv)s::vector
        limit %(k)s
    """, {"qv": str(query_vector), "k": top_k, **params})
    return [Hit(*row[:8], score=float(row[8]), semantic_rank=i + 1)
            for i, row in enumerate(cur.fetchall())]


def _keyword_expression(cur, query: str, sections: list[str] | None) -> str:
    """
    Choose AND or OR for this question, by counting what AND would return.

    A question whose distinctive terms co-occur is served far better by AND.
    Falling back to OR only when AND is too thin keeps precision where it is
    available and recall where it is not.
    """
    where, params = _filters(sections, None)
    cur.execute(f"""
        select count(*) from chunks c
        where c.content_tsv @@ {_AND_TSQUERY} {where}
    """, {"q": query, **params})
    n_and = cur.fetchone()[0]
    return _AND_TSQUERY if n_and >= KEYWORD_MIN_AND_HITS else _OR_TSQUERY


def search_keyword(cur, query: str, top_k: int = C.RETRIEVAL_TOP_K,
                   sections: list[str] | None = None,
                   expression: str | None = None,
                   tickers: list[str] | None = None) -> list[Hit]:
    where, params = _filters(sections, tickers)
    expr = expression or _keyword_expression(cur, query, sections)
    cur.execute(f"""
        select {_SELECT_FIELDS},
               ts_rank(c.content_tsv, {expr}) as score
        from chunks c
        join documents d using (doc_id)
        where c.content_tsv @@ {expr} {where}
        order by score desc
        limit %(k)s
    """, {"q": query, "k": top_k, **params})
    return [Hit(*row[:8], score=float(row[8]), keyword_rank=i + 1)
            for i, row in enumerate(cur.fetchall())]


def search_hybrid(cur, query: str, query_vector: list[float],
                  top_k: int = C.RETRIEVAL_TOP_K, pool: int = C.RETRIEVAL_POOL,
                  rrf_k: int = C.RRF_K,
                  sections: list[str] | None = None,
                  tickers: list[str] | None = None) -> list[Hit]:
    """
    Reciprocal Rank Fusion over both paths.

        score(chunk) = Σ 1 / (rrf_k + rank_in_that_list)

    RRF uses ranks, not raw scores, so cosine distance and ts_rank never have to
    be put on a comparable scale — which is the whole reason to prefer it over
    weighted score blending, where the weights are guesswork.

    A full outer join is required: a chunk found by only one path must still
    compete, scored on the one rank it has.
    """
    where, params = _filters(sections, tickers)
    expr = _keyword_expression(cur, query, sections)
    # documents is joined inside each CTE because the ticker filter lives there.
    cur.execute(f"""
        with semantic as (
            select c.chunk_id,
                   row_number() over (order by c.embedding <=> %(qv)s::vector) as rank
            from chunks c
            join documents d using (doc_id)
            where c.embedding is not null {where}
            order by c.embedding <=> %(qv)s::vector
            limit %(pool)s
        ),
        keyword as (
            select c.chunk_id,
                   row_number() over (
                       order by ts_rank(c.content_tsv, {expr}) desc
                   ) as rank
            from chunks c
            join documents d using (doc_id)
            where c.content_tsv @@ {expr} {where}
            limit %(pool)s
        ),
        fused as (
            select coalesce(s.chunk_id, k.chunk_id) as chunk_id,
                   s.rank as semantic_rank,
                   k.rank as keyword_rank,
                   coalesce(1.0 / (%(rrf)s + s.rank), 0)
                 + coalesce(1.0 / (%(rrf)s + k.rank), 0) as rrf_score
            from semantic s
            full outer join keyword k using (chunk_id)
        )
        select {_SELECT_FIELDS}, f.rrf_score, f.semantic_rank, f.keyword_rank
        from fused f
        join chunks c using (chunk_id)
        join documents d using (doc_id)
        order by f.rrf_score desc
        limit %(k)s
    """, {"q": query, "qv": str(query_vector), "k": top_k,
          "pool": pool, "rrf": rrf_k, **params})

    return [Hit(*row[:8], score=float(row[8]),
                semantic_rank=row[9], keyword_rank=row[10])
            for row in cur.fetchall()]


def search(cur, query: str, query_vector: list[float],
           top_k: int = C.RETRIEVAL_TOP_K, sections: list[str] | None = None,
           auto_company: bool = True, **kw) -> list[Hit]:
    """
    Hybrid retrieval with the company constraint applied when the question
    carries one.

    When a question names one company, the search is restricted to it. When it
    names two -- every comparative question does -- the budget is split and each
    company is searched separately, then interleaved.

    That split is the point. A comparative needs evidence from both filings, and
    a single ranking has no mechanism to guarantee it: measured coverage on
    comparatives was 0.25, because the ranking spent all eight slots on whichever
    company matched more strongly. Quotas make the guarantee structural instead
    of hoping the ranking provides it.
    """
    tickers = detect_companies(query) if auto_company else []

    if len(tickers) <= 1:
        return search_hybrid(cur, query, query_vector, top_k=top_k,
                             sections=sections, tickers=tickers or None, **kw)

    per_company = max(1, top_k // len(tickers))
    buckets = [
        search_hybrid(cur, query, query_vector, top_k=per_company,
                      sections=sections, tickers=[t], **kw)
        for t in tickers
    ]

    # Interleaved so the top of each company's list appears before the tail of
    # any other: a prompt truncated early still sees both sides.
    out, seen = [], set()
    for i in range(per_company):
        for bucket in buckets:
            if i < len(bucket) and bucket[i].chunk_id not in seen:
                seen.add(bucket[i].chunk_id)
                out.append(bucket[i])
    return out[:top_k]


# ─────────────────────────────────────────────────────────────────────
# Degradations for the sabotage test
# ─────────────────────────────────────────────────────────────────────
# Each one disables a specific capability. The point is to confirm a metric
# collapses; a degradation that moves nothing means the harness has a blind spot,
# and that is a finding rather than a pass.

def degraded_starved(cur, query, qv, **kw):
    """top_k = 1. Recall@k and MRR should collapse."""
    return search_hybrid(cur, query, qv, top_k=1, pool=1, **kw)


def degraded_semantic_only(cur, query, qv, **kw):
    """No keyword path. Questions hinging on exact terms should fail."""
    return search_semantic(cur, qv, **kw)


# All four degradations take (cur, query, qv) so the harness can call them
# uniformly. Two of them ignore one argument, and that is fine; a uniform
# signature is worth more than avoiding an unused parameter.


def degraded_keyword_only(cur, query, qv, **kw):
    """No semantic path. Questions phrased differently to the filing should fail."""
    return search_keyword(cur, query, **kw)


def degraded_no_company_filter(cur, query, qv, **kw):
    """
    Hybrid retrieval without the company constraint: the behaviour measured
    before it existed. Kept so the harness can put a number on what it is worth
    rather than asserting it.
    """
    return search_hybrid(cur, query, qv, **kw)


def degraded_or_keyword(cur, query, qv, **kw):
    """
    Force OR on the keyword side, reproducing the defect that made hybrid worse
    than semantic alone on factual questions. Included so the harness can put a
    number on how much the AND-first rule is worth.
    """
    return search_keyword(cur, query, expression=_OR_TSQUERY, **kw)
