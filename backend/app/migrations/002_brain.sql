-- Searchable chunks of the brain (markdown notes). The files stay the source of truth;
-- this table is a rebuildable index (see app/brain.py: reindex).
CREATE TABLE IF NOT EXISTS brain_chunks (
    note   TEXT NOT NULL,
    idx    INTEGER NOT NULL,
    folder TEXT NOT NULL DEFAULT '',
    body   TEXT NOT NULL,
    tsv    TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', note || ' ' || body)) STORED,
    PRIMARY KEY (note, idx)
);
CREATE INDEX IF NOT EXISTS brain_chunks_tsv_idx ON brain_chunks USING GIN (tsv);
