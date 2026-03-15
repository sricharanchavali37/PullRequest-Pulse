-- schema.sql — PRPulse database schema
-- Run once at worker startup via db/client.py init_db()
-- Safe to run repeatedly — all statements use IF NOT EXISTS

-- ── Tables ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pull_requests (
    id         SERIAL PRIMARY KEY,
    pr_number  INT  NOT NULL UNIQUE,   -- UNIQUE enforces idempotency at DB level:
                                       -- retries cannot insert duplicates
    author     TEXT,
    repo_owner TEXT,
    repo_name  TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pr_analysis (
    id            SERIAL PRIMARY KEY,
    pr_number     INT   NOT NULL,
    files_changed INT,
    lines_added   INT,
    lines_removed INT,
    risk_score    FLOAT,
    risk_level    TEXT,
    analyzed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key ensures an analysis row can only exist if the PR row
    -- exists first.  Prevents orphan analysis rows.
    CONSTRAINT fk_pr
        FOREIGN KEY (pr_number)
        REFERENCES pull_requests(pr_number)
        ON DELETE CASCADE
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
-- Created with IF NOT EXISTS (Postgres 9.5+) so re-running is safe.

CREATE INDEX IF NOT EXISTS idx_pull_requests_pr_number
    ON pull_requests(pr_number);

CREATE INDEX IF NOT EXISTS idx_pr_analysis_pr_number
    ON pr_analysis(pr_number);