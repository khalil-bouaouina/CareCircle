-- The nine tables from architecture.md section 4, plus the observation_code seed table.
-- List columns hold JSON text. Timestamps are ISO 8601 text.
-- There is no religion column. capacity_mode is three-valued. Scope lives on the statement.

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
    role      TEXT NOT NULL,                             -- primary_caregiver | family | worker
    language  TEXT NOT NULL DEFAULT 'fr'
);

CREATE TABLE IF NOT EXISTS preference_statement (
    id                  INTEGER PRIMARY KEY,
    elder_id            INTEGER NOT NULL REFERENCES elder(id),
    statement           TEXT NOT NULL,                   -- one plain sentence, written by a human
    category            TEXT NOT NULL,                   -- care | communication | routine | observance | safety
    applies_to_tasks    TEXT NOT NULL DEFAULT '[]',      -- JSON list; empty = all tasks
    excluded_tasks      TEXT NOT NULL DEFAULT '[]',      -- JSON list
    time_start          TEXT,                            -- "HH:MM" or NULL = always
    time_end            TEXT,
    hidden_from         TEXT NOT NULL DEFAULT '[]',      -- JSON list of person ids
    status              TEXT NOT NULL DEFAULT 'active',  -- active | proposed | rejected | retired
    source_checkout_id  INTEGER REFERENCES checkout(id),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_statement_elder_status ON preference_statement(elder_id, status);

CREATE TABLE IF NOT EXISTS visit (
    id                INTEGER PRIMARY KEY,
    elder_id          INTEGER NOT NULL REFERENCES elder(id),
    worker_name       TEXT NOT NULL,
    worker_role       TEXT NOT NULL,
    worker_language   TEXT NOT NULL DEFAULT 'fr',
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
    submitted_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observation_code (
    code                 TEXT PRIMARY KEY,
    label_en             TEXT NOT NULL,
    label_fr             TEXT NOT NULL,
    category             TEXT NOT NULL,
    suggested_statement  TEXT                            -- fold-back template; NULL = never proposes
);

CREATE TABLE IF NOT EXISTS proposed_update (
    id                   INTEGER PRIMARY KEY,
    elder_id             INTEGER NOT NULL REFERENCES elder(id),
    source_checkout_id   INTEGER REFERENCES checkout(id),
    suggested_statement  TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'pending', -- pending | approved | rejected
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

-- User accounts and elder circle relationships for real authentication
CREATE TABLE IF NOT EXISTS user_account (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_elder_link (
    user_id       INTEGER NOT NULL REFERENCES user_account(id),
    elder_id      INTEGER NOT NULL REFERENCES elder(id),
    person_id     INTEGER REFERENCES person(id),
    role          TEXT NOT NULL, -- primary_caregiver | family | elder
    PRIMARY KEY (user_id, elder_id)
);

