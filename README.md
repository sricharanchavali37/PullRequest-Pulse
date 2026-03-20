# PRPulse — Pull Request Intelligence Platform

> **An event-driven system that automatically analyses every GitHub Pull Request, computes a risk score, detects breaking changes, and exposes the results through a REST API and real-time dashboard.**

---

## What problem does this solve?

GitHub tells you *what* was merged. It doesn't tell you *how risky* it was.

| GitHub alone | PRPulse |
|---|---|
| No risk scoring | Automatic LOW / MEDIUM / HIGH score on every PR |
| No breaking-change detection | Detects function signature changes, route deletions, config edits |
| No real-time analysis | Live dashboard updates via Server-Sent Events |
| No reviewer analytics | Review time, workload, and velocity metrics |
| Delayed or no reporting | Event-driven — analysis runs within seconds of PR open |

PRPulse is an **analytics and intelligence layer on top of GitHub**, not a replacement for it.

---

## Architecture

```
GitHub
  │
  │  POST /webhook (pull_request.opened)
  ▼
┌─────────────────────────────────┐
│  Webhook Service  (FastAPI :8000)│   ← receives event, returns HTTP 200 in < 50ms
└────────────────┬────────────────┘
                 │  XADD
                 ▼
┌─────────────────────────────────┐
│  Redis Stream                   │   ← prpulse:events:raw
│  (Pending Entries List)         │   ← crash-safe: events survive worker restarts
└────────────────┬────────────────┘
                 │  XREADGROUP
                 ▼
┌─────────────────────────────────┐
│  Analysis Worker  (Python async) │
│                                 │
│  1. GitHub API → fetch PR files │   ← paginated, retried on failure
│  2. Diff Parser → 4 signals     │   ← config change, large diff, fn sig, route delete
│  3. Risk Scorer → 0–100         │   ← LOW 0-30 / MEDIUM 31-60 / HIGH 61-100
│  4. PostgreSQL → persist        │   ← idempotent upsert
│  5. XACK → confirm done         │   ← only after DB write succeeds
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  PostgreSQL                     │   ← pull_requests + pr_analysis tables
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Query API  (FastAPI :8001)     │   ← REST endpoints for repos, PRs, metrics
└────────────────┬────────────────┘
                 │  (Phase 6)
                 ▼
┌─────────────────────────────────┐
│  React Dashboard                │   ← live PR feed via Server-Sent Events
└─────────────────────────────────┘

Failure path:
  Worker fails 3 times → XADD prpulse:events:failed (Dead Letter Queue)
  Worker crashes mid-process → XAUTOCLAIM reclaims after 60s (runs every 30s)
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Webhook service | FastAPI + Python | Async, returns HTTP 200 in < 50ms |
| Event queue | Redis Streams | Messages survive crashes, consumer groups for scaling |
| Analysis worker | Python asyncio | Non-blocking GitHub API calls, retries, backoff |
| Storage | PostgreSQL + asyncpg | Persistent analytics, idempotent inserts |
| Query API | FastAPI + asyncpg pool | REST endpoints, layered architecture |
| Dashboard (Phase 6) | React + Recharts + SSE | Live updates, no polling |
| Infrastructure | Docker Compose | One command to run the full stack |

---

## Database Schema

```sql
-- Table 1: one row per pull request
CREATE TABLE pull_requests (
    id         SERIAL PRIMARY KEY,
    pr_number  INT  NOT NULL UNIQUE,   -- UNIQUE = safe to retry (ON CONFLICT DO NOTHING)
    author     TEXT,
    repo_owner TEXT,
    repo_name  TEXT,
    files_changed INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: one row per completed analysis
CREATE TABLE pr_analysis (
    id            SERIAL PRIMARY KEY,
    pr_number     INT   NOT NULL,
    files_changed INT,
    lines_added   INT,
    lines_removed INT,
    risk_score    FLOAT,
    risk_level    TEXT,               -- LOW / MEDIUM / HIGH
    analyzed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pr FOREIGN KEY (pr_number) REFERENCES pull_requests(pr_number)
);
```

The FK constraint means `pr_analysis` can never have a row without a parent in `pull_requests`. The worker always inserts the PR row first, then the analysis row.

---

## Risk Scoring

```
files_changed > 10          → +15 points
lines_added   > 300         → +20 points
lines_removed > 200         → +10 points
any breaking change found   → +40 points
config file changed         → +15 points
─────────────────────────────────────────
0–30  → LOW    (safe to merge)
31–60 → MEDIUM (review carefully)
61–100→ HIGH   (flag for discussion)
```

**Breaking change signals detected from diff patch text:**
- `config_file_change` — `.env`, `settings.yaml`, `config.json` etc. modified
- `large_file_change` — any single file with 200+ lines added or removed
- `function_signature_change` — `def function(` removed AND re-added differently in same patch
- `route_deleted` — `@app.route(` or `@router.get(` removed from diff

---

## Project Structure

```
PullRequestPulse/
│
├── services/
│   ├── webhook/                    ← Phase 1: receives GitHub webhooks
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py             ← FastAPI app entrypoint
│   │       ├── routers/
│   │       │   ├── webhook.py      ← POST /webhook route
│   │       │   └── health.py       ← GET /health route
│   │       └── security/
│   │           └── signature.py    ← HMAC verification (stub)
│   │
│   ├── worker/                     ← Phases 2–4: analysis pipeline
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py             ← worker entrypoint
│   │       ├── worker.py           ← XREADGROUP loop + retry + DLQ + XAUTOCLAIM
│   │       ├── config.py           ← env vars (Redis, DB, GitHub)
│   │       ├── github/
│   │       │   └── client.py       ← GitHub API client, pagination, rate-limit
│   │       ├── diff/
│   │       │   └── parser.py       ← diff analysis, signal detection
│   │       ├── risk/
│   │       │   └── scorer.py       ← risk scoring engine
│   │       ├── models/
│   │       │   └── pr_data.py      ← PRAnalysis + BreakingChange dataclasses
│   │       └── db/
│   │           ├── client.py       ← asyncpg pool lifecycle
│   │           └── repository.py   ← SQL queries (idempotent inserts)
│   │   └── db/
│   │       └── schema.sql          ← table definitions, auto-run on startup
│   │
│   └── api/                        ← Phase 5: REST query API
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── main.py             ← FastAPI app, lifespan, exception handlers
│           ├── config.py           ← DATABASE_URL, pagination settings
│           ├── db/database.py      ← asyncpg pool
│           ├── api/                ← route handlers (repos, metrics, analytics, health)
│           ├── repositories/       ← raw SQL queries
│           ├── services/           ← business logic layer
│           └── schemas/            ← Pydantic response models
│
├── shared/
│   └── redis/
│       ├── client.py               ← Redis connection factory (stub — fill in)
│       └── constants.py            ← stream names, group names (stub — fill in)
│
├── scripts/
│   └── inspect_stream.py           ← debug tool: read Redis stream entries
│
├── docker-compose.yml              ← postgres + redis + api (webhook + worker TBD)
└── .env.example                    ← template for environment variables
```

---

## Development Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Webhook ingestion → Redis Stream | ✅ Complete |
| 2 | Redis Streams consumer worker | ✅ Complete |
| 3 | GitHub API + diff parser + risk scorer | ✅ Complete |
| 4 | PostgreSQL persistence + retry + DLQ + crash recovery | ✅ Complete |
| 5 | Query API (REST endpoints) | ⚠️ Mostly done — 3 gaps remaining |
| 6 | React dashboard + Server-Sent Events | 🔷 Up next |

**Phase 5 gaps (3 small tasks):**
1. Fill `shared/redis/client.py` — currently an empty file
2. Fill `shared/redis/constants.py` — currently an empty file
3. Add `webhook` and `worker` services to `docker-compose.yml`

---

## Running Locally

### Prerequisites
- Python 3.10+
- Docker Desktop (for Redis and PostgreSQL)
- A GitHub personal access token with `repo` scope

### 1. Clone and configure

```bash
git clone https://github.com/sricharanchavali37/PullRequest-Pulse.git
cd PullRequest-Pulse
```

Create `services/worker/.env`:

```env
GITHUB_TOKEN=your_personal_access_token
GITHUB_OWNER=your_github_username
GITHUB_REPO=your_test_repo_name
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/prpulse
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 2. Start infrastructure

```bash
# Start Redis
docker run -d --name prpulse_redis -p 6379:6379 redis:7-alpine

# Start PostgreSQL
docker run -d --name prpulse_postgres \
  -e POSTGRES_DB=prpulse \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16-alpine
```

### 3. Install dependencies

```bash
# Webhook service
cd services/webhook
pip install fastapi uvicorn redis[asyncio]

# Worker
cd ../worker
pip install -r requirements.txt

# API
cd ../api
pip install -r requirements.txt
```

### 4. Start services (3 terminals)

```bash
# Terminal 1 — Webhook service
cd services/webhook
uvicorn app.main:app --port 8000 --reload

# Terminal 2 — Analysis worker
cd services/worker
python -m app.main

# Terminal 3 — Query API
cd services/api
uvicorn app.main:app --port 8001 --reload
```

### 5. Test the pipeline

```bash
# Send a test webhook event
curl -X POST http://127.0.0.1:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"number": 1}'

# Check what landed in Redis
redis-cli XRANGE prpulse:events:raw - +

# Check the analysis results in the API
curl http://localhost:8001/repos
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/repos` | List all tracked repositories |
| GET | `/repos/{repo_id}/prs` | Paginated PR list with risk scores |
| GET | `/repos/{repo_id}/metrics` | Aggregated PR size, risk, merge stats |
| GET | `/repos/{repo_id}/risk-distribution` | Count of LOW / MEDIUM / HIGH PRs |
| GET | `/repos/{repo_id}/review-performance` | Reviewer analytics |

---

## Reliability Design

| Scenario | How it's handled |
|---|---|
| Worker crashes mid-processing | Message stays in Redis PEL, reclaimed by XAUTOCLAIM after 60s |
| GitHub API returns 5xx | Retry up to 3 times with 1s → 2s → 4s backoff |
| Same PR processed twice | `ON CONFLICT DO NOTHING` on the PostgreSQL insert — no duplicate, no error |
| All 3 retries fail | Event moved to `prpulse:events:failed` (DLQ) for manual inspection |
| DB write fails | XACK is never called — message stays in PEL for retry |

**Key rule:** `XACK` is called **only after** the PostgreSQL write commits successfully. This one ordering decision is what makes the entire pipeline crash-safe.

---

## What's Coming in Phase 6

- Worker publishes analysis results to `prpulse:notifications` stream
- API service exposes `GET /events/stream` (Server-Sent Events)
- React dashboard with live PR feed — new PRs appear within seconds, no refresh
- Risk distribution chart and weekly velocity metrics (Recharts)
- Full Docker Compose stack with all services

---

## For Viewers

A detailed visual project guide (architecture diagrams, phase walkthroughs, Q&A) is available as `README.html` in the root of this repository. Open it in any browser.
