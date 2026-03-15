\# PRPulse — Pull Request Intelligence Platform



PRPulse analyzes GitHub Pull Requests and computes a \*\*risk score\*\* based on code changes.



The system uses an \*\*event-driven architecture\*\* built with Redis Streams and an async worker pipeline.



\---



\## Architecture



```mermaid

flowchart TD



A\[GitHub Webhook] --> B\[FastAPI Webhook Service]



B -->|XADD| C\[Redis Stream<br>prpulse:events:raw]



C -->|XREADGROUP| D\[Worker Service]



D --> E\[GitHub API]

D --> F\[Diff Parser]

D --> G\[Risk Scoring]



E --> D

F --> D

G --> D



D --> H\[PostgreSQL]



D -->|Failures| I\[Redis Dead Letter Queue<br>prpulse:events:failed]



```
# PRPulse — Pull Request Intelligence Platform

PRPulse analyzes GitHub Pull Requests and computes a **risk score** based on code changes.

The system uses an **event-driven architecture** built with Redis Streams and an async worker pipeline.

---

## Architecture

```mermaid
flowchart TD

A[GitHub Webhook] --> B[FastAPI Webhook Service]

B -->|XADD| C[Redis Stream<br>prpulse:events:raw]

C -->|XREADGROUP| D[Worker Service]

D --> E[GitHub API]
D --> F[Diff Parser]
D --> G[Risk Scoring]

E --> D
F --> D
G --> D

D --> H[PostgreSQL]

D -->|Failures| I[Redis Dead Letter Queue<br>prpulse:events:failed]

```
## System Overview

PRPulse processes Pull Requests through an event pipeline:

1. GitHub sends a webhook event
2. FastAPI webhook service writes the event into Redis Stream
3. Worker service consumes events using Redis consumer groups
4. Worker fetches PR metadata from GitHub API
5. Diff parser extracts change signals
6. Risk engine calculates a deterministic risk score
7. Results are stored in PostgreSQL
8. Worker acknowledges the Redis event

If processing fails after retries, the event is sent to a Dead Letter Queue.



## Project Structure

```
PullRequestPulse
│
├── services
│   ├── webhook
│   │   └── FastAPI webhook ingestion service
│   │
│   └── worker
│       ├── app
│       │   ├── worker.py          # event processing worker
│       │   ├── config.py          # environment configuration
│       │   ├── github             # GitHub API client
│       │   ├── diff               # diff parser
│       │   ├── risk               # risk scoring engine
│       │   └── db                 # database layer
│       │       ├── client.py
│       │       └── repository.py
│       │
│       └── db
│           └── schema.sql         # database schema
│
├── shared
│   └── redis                     # redis utilities
│
└── docker-compose.yml
```


## Environment Variables

Create a `.env` file inside `services/worker`.

Example:

```
GITHUB_TOKEN=your_token
GITHUB_OWNER=your_username
GITHUB_REPO=repository_name
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/prpulse
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Running the System

### Start Redis

```
docker run -d -p 6379:6379 redis:7
```

### Start Webhook Service

```
cd services/webhook
uvicorn app.main:app --reload --port 8000
```

### Start Worker

```
cd services/worker
python -m app.main
```

### Trigger Webhook

```
curl -X POST http://127.0.0.1:8000/webhook \
-H "Content-Type: application/json" \
-d "{\"number\":1}"
```

## Development Phases

Phase-1  
Webhook ingestion → Redis Stream

Phase-2  
Redis Streams consumer worker

Phase-3  
PR analysis engine (GitHub API + diff parsing + risk scoring)

Phase-4  
Persistence + reliability  
(PostgreSQL, retries, DLQ, recovery)

Upcoming phases:

Phase-5  
Query API

Phase-6  
Dashboard UI

Phase-7  
Metrics & observability

Phase-8  
Event replay tools


