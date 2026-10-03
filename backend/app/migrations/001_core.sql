-- Core office state. Applied once by db.migrate(); tracked in schema_version.

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    state       TEXT NOT NULL DEFAULT 'next',
    updated_at  DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS tasks_state_idx ON tasks (state);

CREATE TABLE IF NOT EXISTS routine_state (
    id    TEXT PRIMARY KEY,
    data  JSONB NOT NULL
);

-- One row per pipeline job. The LangGraph checkpointer holds the graph state;
-- this table is the queryable summary the API and UI read.
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,              -- client | own
    title       TEXT NOT NULL,
    stage       TEXT NOT NULL,
    status      TEXT NOT NULL,              -- running | waiting | parked | done | killed | failed
    data        JSONB NOT NULL,
    created_at  DOUBLE PRECISION NOT NULL,
    updated_at  DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs (status);

-- A lead's (or the owner's) decision on one stage of one job. One row per
-- (job, stage, role): approving twice is an idempotent no-op.
CREATE TABLE IF NOT EXISTS approvals (
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    stage       TEXT NOT NULL,
    role        TEXT NOT NULL,              -- lead seat id, or "owner"
    verdict     TEXT NOT NULL,              -- PASS | FAIL
    note        TEXT NOT NULL DEFAULT '',
    evidence    JSONB NOT NULL DEFAULT '[]'::jsonb,
    actor       TEXT NOT NULL,              -- agent id, or "owner"
    at          DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (job_id, stage, role)
);

CREATE TABLE IF NOT EXISTS evidence (
    id          TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    stage       TEXT NOT NULL,
    kind        TEXT NOT NULL,              -- check | memo | patch | log | probe
    title       TEXT NOT NULL,
    ok          BOOLEAN,
    body        JSONB NOT NULL,
    at          DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS evidence_job_idx ON evidence (job_id, stage);

-- Connector calls, written BEFORE the call executes.
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    at          DOUBLE PRECISION NOT NULL,
    agent       TEXT NOT NULL,
    dept        TEXT NOT NULL,
    server      TEXT NOT NULL,
    operation   TEXT NOT NULL,
    resource    TEXT NOT NULL,
    allowed     BOOLEAN NOT NULL,
    reason      TEXT NOT NULL DEFAULT ''
);

-- Every metered model call (llm.RunMeter).
CREATE TABLE IF NOT EXISTS run_costs (
    id             BIGSERIAL PRIMARY KEY,
    at             DOUBLE PRECISION NOT NULL,
    label          TEXT NOT NULL,
    model_pinned   TEXT NOT NULL,
    model_seen     TEXT NOT NULL,
    input_tokens   INTEGER NOT NULL,
    output_tokens  INTEGER NOT NULL,
    usd            DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS run_costs_at_idx ON run_costs (at);

-- Small named counters, e.g. how many Tier 1 previews the owner has clicked.
CREATE TABLE IF NOT EXISTS counters (
    name   TEXT PRIMARY KEY,
    value  INTEGER NOT NULL
);
