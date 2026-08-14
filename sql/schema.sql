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
