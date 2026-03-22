-- migration_step2.sql
-- Step 2: Tier-3 schema additions
--
-- Safe to run on an existing database — every statement uses
-- IF NOT EXISTS or ADD COLUMN IF NOT EXISTS.
-- Running this twice produces no errors and no duplicate data.
--
-- Run this ONCE manually before deploying the new worker.
-- After this migration, schema.sql is also updated so new deployments
-- get all tables from scratch.

-- ── 1. Add lifecycle columns to pull_requests ─────────────────────────────────
-- These columns track the full PR lifecycle after it is opened.

ALTER TABLE pull_requests
    ADD COLUMN IF NOT EXISTS state                TEXT      DEFAULT 'open',
    ADD COLUMN IF NOT EXISTS title                TEXT,
    ADD COLUMN IF NOT EXISTS base_branch          TEXT,
    ADD COLUMN IF NOT EXISTS head_branch          TEXT,
    ADD COLUMN IF NOT EXISTS github_pr_id         BIGINT,
    ADD COLUMN IF NOT EXISTS first_review_at      TIMESTAMP,
    ADD COLUMN IF NOT EXISTS merged_at            TIMESTAMP,
    ADD COLUMN IF NOT EXISTS closed_at            TIMESTAMP,
    ADD COLUMN IF NOT EXISTS cycle_time_hours     FLOAT,
    ADD COLUMN IF NOT EXISTS review_latency_hours FLOAT;

-- ── 2. New table: repositories ────────────────────────────────────────────────
-- Replaces hardcoded GITHUB_OWNER / GITHUB_REPO env vars.
-- Each row is one tracked repository.

CREATE TABLE IF NOT EXISTS repositories (
    id             TEXT        PRIMARY KEY,
    -- stable 8-char hex hash of owner+name
    -- e.g. MD5('sricharanchavali37/PullRequest-Pulse')[:8]

    owner          TEXT        NOT NULL,
    name           TEXT        NOT NULL,
    github_id      BIGINT,
    -- GitHub's internal repo ID from webhook payload (repository.id)
    -- not required but useful for deduplication

    created_at     TIMESTAMP   DEFAULT NOW(),

    CONSTRAINT uq_repo_owner_name UNIQUE (owner, name)
    -- prevents the same repo being registered twice
    -- ON CONFLICT on this constraint = safe idempotent upsert
);

-- ── 3. New table: pr_reviews ──────────────────────────────────────────────────
-- One row per review submitted event.
-- Tracks who reviewed, when, what state, and how long after PR open.

CREATE TABLE IF NOT EXISTS pr_reviews (
    id                   SERIAL      PRIMARY KEY,
    pr_number            INT         NOT NULL,
    repo_owner           TEXT        NOT NULL,
    repo_name            TEXT        NOT NULL,
    reviewer             TEXT        NOT NULL,
    state                TEXT        NOT NULL,
    -- 'approved' | 'changes_requested' | 'commented'
    submitted_at         TIMESTAMP   NOT NULL,
    review_latency_hours FLOAT,
    -- (submitted_at - pull_requests.created_at) in hours
    -- computed at insert time so queries never re-derive it

    CONSTRAINT fk_pr_review
        FOREIGN KEY (pr_number)
        REFERENCES pull_requests(pr_number)
        ON DELETE CASCADE
);

-- ── 4. New table: weekly_snapshots ────────────────────────────────────────────
-- Pre-aggregated weekly metrics per repo.
-- Written by the weekly snapshot job (Step 4).
-- Dashboard reads 12 rows instead of aggregating all PRs on every request.

CREATE TABLE IF NOT EXISTS weekly_snapshots (
    id                       SERIAL  PRIMARY KEY,
    repo_owner               TEXT    NOT NULL,
    repo_name                TEXT    NOT NULL,
    week_start               DATE    NOT NULL,
    -- Monday of the week this snapshot covers

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
    -- ON CONFLICT DO UPDATE = safe to re-run the snapshot job any time
);

-- ── 5. Indexes ────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_pr_reviews_reviewer
    ON pr_reviews(reviewer);

CREATE INDEX IF NOT EXISTS idx_pr_reviews_submitted
    ON pr_reviews(submitted_at);

CREATE INDEX IF NOT EXISTS idx_pr_reviews_pr_number
    ON pr_reviews(pr_number);

CREATE INDEX IF NOT EXISTS idx_pull_requests_state
    ON pull_requests(state);

CREATE INDEX IF NOT EXISTS idx_pull_requests_merged_at
    ON pull_requests(merged_at)
    WHERE merged_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_weekly_snapshots_repo_week
    ON weekly_snapshots(repo_owner, repo_name, week_start DESC);
