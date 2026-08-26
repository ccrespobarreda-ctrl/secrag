-- SEC filings RAG: schema
--
-- One database serves both retrieval paths. pgvector handles semantic search,
-- Postgres full-text search handles keyword search, and the fusion happens in
-- SQL. No separate vector store to keep in sync.
--
-- THIS FILE IS IDEMPOTENT, AND THAT IS NOT A STYLE CHOICE
--
-- It used to open with `drop table if exists chunks cascade`. Running it twice
-- was therefore destructive, and what it destroyed was not the rows: it was the
-- chunk_id sequence.
--
-- eval/questions.yaml carries 88 gold_chunk_ids across 34 questions. Those are
-- serial ids. Dropping the table resets the sequence, the next load reissues the
-- same numbers to whatever chunks the current chunking produces, and every
-- Recall@k figure is then measured against labels pointing at different text.
-- Nothing errors. The evaluation simply stops meaning anything.
--
-- So the drops live in sql/reset.sql, which has to be asked for by name, and
-- src/verify_labels.py exists to confirm the labels still point where they did.

create extension if not exists vector;

-- HOW WIDE THE APPROXIMATE SEARCH RUNS, DECLARED RATHER THAN INHERITED
--
-- HNSW is approximate: it walks a graph instead of scanning all 4,169 vectors,
-- and hnsw.ef_search decides how many candidates it keeps alive while walking.
-- It is a session or database setting, not a property of the index, so a fresh
-- clone inherits whatever the local pgvector build defaults to. Two people
-- running the same evaluation against the same corpus could then get different
-- numbers with nothing in the harness noticing.
--
-- Every published figure was measured at 40, which is pgvector's default. That
-- is stated here rather than assumed.
--
-- 200 was tried on 14 August and changed nothing: eval/results/retrieval.json
-- and eval/results/retrieval_ef200.json, seven minutes apart, agree on every
-- semantic figure to six decimal places. The reason is the size of the index —
-- with four thousand vectors the graph is small enough that a width of 40
-- already returns what an exact search would. The setting starts to matter at
-- hundreds of thousands of vectors, not thousands.
--
-- Raising it later is not a tuning knob. It is a new measurement, and every
-- published retrieval figure would have to be reissued with it.
--
-- Applied to whatever database this file is run against, rather than to a name
-- written here. docker-compose.yml creates `secrag`; the managed instance this
-- was measured on is `neondb`; hardcoding either one makes the file fail on the
-- other, quietly leaving the setting inherited on whichever path was not named.
--
-- ALTER DATABASE takes effect on new connections, not the one running this, so
-- reconnect before measuring. src/check_db_settings.py reports the live value.
do $$
begin
    execute format('alter database %I set hnsw.ef_search = 40',
                   current_database());
exception
    when insufficient_privilege then
        raise notice 'Could not set hnsw.ef_search: not the database owner. '
                     'Set it per session instead: SET hnsw.ef_search = 40;';
end
$$;

-- A note on the text search dictionary, for the same reason.
--
-- The generated column below names 'english' explicitly, and so do both tsquery
-- expressions in src/retrieve.py. That is deliberate: the managed Postgres this
-- runs on sets default_text_search_config to 'simple', which does no stemming
-- and strips no stopwords. Relying on the server default would have indexed
-- with one dictionary and queried with another — "revenues" would stop matching
-- "revenue" — and nothing would have raised an error.

create table if not exists documents (
    doc_id        text primary key,       -- e.g. NKE-10-K-2026
    ticker        text not null,
    company       text not null,
    cik           bigint not null,
    form_type     text not null,
    fiscal_year   int not null,
    filed_date    date not null,
    source_url    text not null,          -- traceable back to EDGAR
    raw_chars     int not null,
    ingested_at   timestamptz not null default now()
);

create table if not exists chunks (
    chunk_id      bigserial primary key,
    doc_id        text not null references documents(doc_id) on delete cascade,

    -- Section metadata is what allows filtered retrieval. Fixed-size chunking
    -- discards the document's own legally mandated structure; this keeps it.
    item_section  text,
    section_title text,

    chunk_index   int not null,           -- order within the document
    token_count   int not null,
    content       text not null,

    embedding     vector(384),            -- bge-small-en-v1.5

    -- Generated, not populated by the loader: it cannot drift out of sync with
    -- content, which is the same reasoning as a computed column in a warehouse.
    content_tsv   tsvector generated always as
                  (to_tsvector('english', content)) stored,

    -- src/load.py upserts on this pair. It is also what makes a reload
    -- deterministic: identical chunks.json in, identical chunk_ids out.
    unique (doc_id, chunk_index)
);

-- HNSW for approximate nearest neighbour. Built after the load, not before:
-- inserting into an existing HNSW index is markedly slower. src/load.py drops
-- and rebuilds these around a bulk load, so they are created here only for a
-- fresh database.
create index if not exists chunks_embedding_idx on chunks
    using hnsw (embedding vector_cosine_ops);

create index if not exists chunks_tsv_idx on chunks using gin (content_tsv);
create index if not exists chunks_section_idx on chunks (doc_id, item_section);
