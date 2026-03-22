-- schema.sql — PRPulse complete database schema (Tier-3 updated)
-- Run once at worker startup via db/client.py init_db()
-- Safe to run repeatedly — all statements use IF NOT EXISTS

-- ── Tables ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS repositories (
    id             TEXT        PRIMARY KEY,
    owner          TEXT        NOT NULL,
    name           TEXT        NOT NULL,
    github_id      BIGINT,
    created_at     TIMESTAMP   DEFAULT NOW(),
    CONSTRAINT uq_repo_owner_name UNIQUE (owner, name)
);

CREATE TABLE IF NOT EXISTS pull_requests (
    id                    SERIAL      PRIMARY KEY,
    pr_number             INT         NOT NULL UNIQUE,
    author                TEXT,
    repo_owner            TEXT,
    repo_name             TEXT,
    state                 TEXT        DEFAULT 'open',
    title                 TEXT,
    base_branch           TEXT,
    head_branch           TEXT,
    github_pr_id          BIGINT,
    first_review_at       TIMESTAMP,
    merged_at             TIMESTAMP,
    closed_at             TIMESTAMP,
    cycle_time_hours      FLOAT,
    review_latency_hours  FLOAT,
    created_at            TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pr_analysis (
    id            SERIAL      PRIMARY KEY,
    pr_number     INT         NOT NULL,
    files_changed INT,
    lines_added   INT,
    lines_removed INT,
    risk_score    FLOAT,
    risk_level    TEXT,
    analyzed_at   TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pr
        FOREIGN KEY (pr_number)
        REFERENCES pull_requests(pr_number)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pr_reviews (
    id                   SERIAL      PRIMARY KEY,
    pr_number            INT         NOT NULL,
    repo_owner           TEXT        NOT NULL,
    repo_name            TEXT        NOT NULL,
    reviewer             TEXT        NOT NULL,
    state                TEXT        NOT NULL,
    submitted_at         TIMESTAMP   NOT NULL,
    review_latency_hours FLOAT,
    CONSTRAINT fk_pr_review
        FOREIGN KEY (pr_number)
        REFERENCES pull_requests(pr_number)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS weekly_snapshots (
    id                       SERIAL  PRIMARY KEY,
    repo_owner               TEXT    NOT NULL,
    repo_name                TEXT    NOT NULL,
    week_start               DATE    NOT NULL,
    prs_opened               INT     DEFAULT 0,
    prs_merged               INT     DEFAULT 0,
    prs_closed_no_merge      INT     DEFAULT 0,
    avg_risk_score           FLOAT   DEFAULT 0,
    avg_cycle_time_hours     FLOAT   DEFAULT 0,
    avg_review_latency_hours FLOAT   DEFAULT 0,
    avg_pr_size              FLOAT   DEFAULT 0,
    high_risk_count          INT     DEFAULT 0,
    computed_at              TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_snapshot_repo_week UNIQUE (repo_owner, repo_name, week_start)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_pull_requests_pr_number
    ON pull_requests(pr_number);

CREATE INDEX IF NOT EXISTS idx_pull_requests_state
    ON pull_requests(state);

CREATE INDEX IF NOT EXISTS idx_pull_requests_merged_at
    ON pull_requests(merged_at)
    WHERE merged_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pr_analysis_pr_number
    ON pr_analysis(pr_number);

CREATE INDEX IF NOT EXISTS idx_pr_reviews_reviewer
    ON pr_reviews(reviewer);

CREATE INDEX IF NOT EXISTS idx_pr_reviews_submitted
    ON pr_reviews(submitted_at);

CREATE INDEX IF NOT EXISTS idx_pr_reviews_pr_number
    ON pr_reviews(pr_number);

CREATE INDEX IF NOT EXISTS idx_weekly_snapshots_repo_week
    ON weekly_snapshots(repo_owner, repo_name, week_start DESC);
