-- Ten tables. List columns hold JSON text. Timestamps are ISO 8601 text.
-- There is no religion column and no "cultural preferences" table: every
-- statement is entered the same way, so there is nowhere to put it, by design.

CREATE TABLE IF NOT EXISTS elder (
    id                INTEGER PRIMARY KEY,
    display_name      TEXT NOT NULL,
    primary_language  TEXT NOT NULL DEFAULT 'fr',
    capacity_mode     TEXT NOT NULL DEFAULT 'self'      -- self | assisted | mandated
);

CREATE TABLE IF NOT EXISTS person (
    id        INTEGER PRIMARY KEY,
    elder_id  INTEGER NOT NULL REFERENCES elder(id),
    name      TEXT NOT NULL,
    role      TEXT NOT NULL                             -- primary_caregiver | family
);

-- Workers are first-class rows, not strings on a visit. Turnover is the problem
-- this product exists for; you cannot count what you do not model.
CREATE TABLE IF NOT EXISTS worker (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,
    language    TEXT NOT NULL DEFAULT 'fr',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preference_statement (
    id                  INTEGER PRIMARY KEY,
    elder_id            INTEGER NOT NULL REFERENCES elder(id),
    statement           TEXT NOT NULL,                   -- one plain sentence, written by a human
    kind                TEXT NOT NULL DEFAULT 'preference',  -- preference | approach
    category            TEXT NOT NULL,                   -- care | communication | routine | observance | safety
    source              TEXT NOT NULL DEFAULT 'family',  -- family | worker | correction
    applies_to_tasks    TEXT NOT NULL DEFAULT '[]',      -- JSON list; empty = all tasks
    excluded_tasks      TEXT NOT NULL DEFAULT '[]',      -- JSON list
    time_start          TEXT,                            -- "HH:MM" or NULL = always
    time_end            TEXT,
    hidden_from         TEXT NOT NULL DEFAULT '[]',      -- JSON list of person ids
    status              TEXT NOT NULL DEFAULT 'active',  -- active | retired
    origin_visit_id     INTEGER REFERENCES visit(id),
    confirmations       INTEGER NOT NULL DEFAULT 0,
    source_checkout_id  INTEGER REFERENCES checkout(id),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL                    -- the delta brief depends on this
);
CREATE INDEX IF NOT EXISTS ix_statement_elder_status ON preference_statement(elder_id, status);

CREATE TABLE IF NOT EXISTS visit (
    id                INTEGER PRIMARY KEY,
    elder_id          INTEGER NOT NULL REFERENCES elder(id),
    worker_id         INTEGER NOT NULL REFERENCES worker(id),
    task_type         TEXT NOT NULL,
    scheduled_start   TEXT NOT NULL,
    scheduled_end     TEXT NOT NULL,
    token_hash        TEXT,
    token_valid_from  TEXT,
    token_expires_at  TEXT,
    state             TEXT NOT NULL DEFAULT 'scheduled', -- scheduled | briefed | completed | expired
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_visit_token_hash ON visit(token_hash);
CREATE INDEX IF NOT EXISTS ix_visit_elder_worker ON visit(elder_id, worker_id);

CREATE TABLE IF NOT EXISTS brief (
    id                      INTEGER PRIMARY KEY,
    visit_id                INTEGER NOT NULL UNIQUE REFERENCES visit(id),
    selected_statement_ids  TEXT NOT NULL DEFAULT '[]',
    rendered_lines_json     TEXT NOT NULL DEFAULT '[]',
    model                   TEXT,
    generated_at            TEXT NOT NULL,
    fallback_used           INTEGER NOT NULL DEFAULT 0
);

-- Append-only. No UPDATE or DELETE anywhere in the codebase.
CREATE TABLE IF NOT EXISTS checkout (
    id                 INTEGER PRIMARY KEY,
    visit_id           INTEGER NOT NULL UNIQUE REFERENCES visit(id),
    completion         TEXT NOT NULL,                    -- yes | partial | no
    observation_codes  TEXT NOT NULL DEFAULT '[]',
    note_text          TEXT,
    handover_note      TEXT,                             -- "for the next person"
    submitted_at       TEXT NOT NULL
);

-- The fixed vocabulary a worker can tap at check-out, seeded from config.
CREATE TABLE IF NOT EXISTS observation_code (
    code      TEXT PRIMARY KEY,
    label_en  TEXT NOT NULL,
    label_fr  TEXT NOT NULL,
    category  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposed_update (
    id                   INTEGER PRIMARY KEY,
    elder_id             INTEGER NOT NULL REFERENCES elder(id),
    source_checkout_id   INTEGER REFERENCES checkout(id),
    origin_kind          TEXT NOT NULL,                   -- handover | pattern | correction
    suggested_kind       TEXT NOT NULL DEFAULT 'approach',-- preference | approach
    suggested_statement  TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'pending', -- pending | accepted | rejected
    decided_by           TEXT,
    decided_at           TEXT,
    created_at           TEXT NOT NULL
);

-- Append-only, elder-readable.
CREATE TABLE IF NOT EXISTS access_log (
    id              INTEGER PRIMARY KEY,
    elder_id        INTEGER NOT NULL REFERENCES elder(id),
    actor_label     TEXT NOT NULL,
    action          TEXT NOT NULL,
    target_summary  TEXT NOT NULL,
    at              TEXT NOT NULL
);
