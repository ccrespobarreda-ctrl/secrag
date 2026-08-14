-- Destroy the corpus tables. Nothing runs this by accident.
--
--     make reset-db CONFIRM=yes
--
-- WHAT THIS COSTS, BEYOND THE ROWS
--
-- chunk_id is a bigserial, and eval/questions.yaml labels 88 of them by number.
-- Dropping chunks drops the sequence with it. The next load starts again at 1
-- and hands those numbers to whatever the current chunking produced.
--
-- If chunks.json is unchanged, the ids land on the same text and the labels
-- survive -- the load is deterministic, because src/chunk.py walks the parsed
-- files in sorted order and src/load.py inserts in that order. If chunking
-- changed at all, they do not, and every retrieval metric is then scored against
-- labels pointing somewhere else. There is no error either way.
--
-- So after any reset and reload:
--
--     python src/verify_labels.py
--
-- which reads each gold chunk and confirms it still contains the answer the
-- label claims it contains.

drop table if exists chunks cascade;
drop table if exists documents cascade;
