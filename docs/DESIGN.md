# EquipTrack design

How the system is put together and why. This describes the code as it is; for running it see the
[README](../README.md), for hosting see [DEPLOYMENT.md](DEPLOYMENT.md).

## The problem

A plant's maintenance knowledge is scattered: machine records in spreadsheets, faults reported verbally,
service history in paper logs, and the manuals that explain an error code in a PDF nobody can find at 2 a.m.
EquipTrack puts the machines, their service history, their open issues, their spare parts and their manuals
in one place, and lets a technician ask the manuals a question in plain words and get a cited answer.

## Users and what they may do

Three roles, ordered: **technician < supervisor < admin**. A role can do everything the roles below it can.

| Action | Technician | Supervisor | Admin |
|---|:-:|:-:|:-:|
| View machines, logs, issues, parts, documents; ask the AI | ✓ | ✓ | ✓ |
| Log maintenance, report issues, claim and resolve issues, use parts | ✓ | ✓ | ✓ |
| Change a machine's status, assign issues, close or reopen issues | | ✓ | ✓ |
| Restock parts, add parts, upload and re-index documents, analytics | | ✓ | ✓ |
| Create, edit, retire or delete machines; delete documents; manage users | | | ✓ |

Where the rule depends only on the role, it is a router dependency (`require_role(Role.SUPERVISOR)`). Where it
depends on the data (using a part is fine, restocking needs a supervisor; who may move an issue depends on
its current status) the check lives in the service layer, next to the rule it protects.

## Architecture

```
Browser ──▶ Next.js (Vercel) ──▶ FastAPI (Docker) ──▶ Postgres 16 + pgvector
            UI + server proxy      routers                  equipment, logs, issues, parts, users
            httpOnly cookie        └─ services (rules)      documents, files, chunks (vector + tsvector)
                                       └─ SQLModel / SQLAlchemy async
                                   background indexing ─▶ fastembed (local, CPU)
                                   /ai/* ─▶ Groq ─fallback─▶ Gemini ─fallback─▶ manual excerpts
Schema changes: Liquibase changelog, applied by compose locally, by the test suite, and by CI/CD in production.
```

- **Layers.** Routers handle HTTP (status codes, validation, auth). Services hold the rules (issue lifecycle,
  stock changes, health score, retrieval). Models map tables. Keeping rules out of routers makes them
  testable on their own and reusable by the seed script.
- **One database.** Relational data, uploaded files (`bytea`), full-text indexes and vector embeddings all
  live in the same Postgres. One backup, one connection string, one migration tool, and joins between a
  chunk and its machine are plain SQL.
- **Async all the way.** FastAPI + asyncpg; CPU-bound work (PDF parsing, embedding) runs in a worker thread
  so it never blocks the event loop.

## Data model

| Table | Holds | Notes |
|---|---|---|
| `equipment` | Machines: name, serial (unique), type, model, location, department, status, dates | Status: active, under maintenance, retired. Retire is a soft delete; hard delete cascades in the database. |
| `maintenance_logs` | One row per service: type, when, duration, cost, who, `next_scheduled_at` | A machine's *current plan* is its latest log's `next_scheduled_at` (`DISTINCT ON`, backed by an index). |
| `issues` | Faults: title, severity, status, error code, reporter, assignee, `resolved_at` | Lifecycle below. |
| `parts` | Spare parts per machine: number, stock, reorder threshold, cost, supplier | Stock changes are one atomic `UPDATE ... WHERE quantity + change >= 0`, so two people can't oversell the last part. |
| `users` | Username, email, role, Argon2 hash, active flag | Logs and issues reference users by id (`performed_by_id`, `reported_by_id`, `assigned_to_id`). |
| `documents` / `document_files` | Metadata and the original file | Indexing status (`is_indexed`, `index_error`) is stored, not lost in a log. |
| `document_chunks` | ~1,000-character pieces of each document | `embedding vector(384)` (HNSW, cosine), `content_tsv` (generated, GIN), `codes text[]` (GIN). |

## Issue lifecycle

```
Open ──technician──▶ In Progress ──technician──▶ Resolved ──supervisor──▶ Closed
                          ▲                          │
                          └──────supervisor──────────┘ (reopen)
```

Any other move returns **422**; a move by too junior a role returns **403**. The service keeps the side
effects consistent: claiming an unassigned issue assigns it to you, resolving sets `resolved_at`, reopening
clears it, every change updates `updated_at`.

## Health score (0-100)

A pure function of facts, so every point is explainable and unit-tested:

| Fact | Points off |
|---|---|
| Each open Critical / High / Medium issue | 35 / 20 / 10 |
| Last maintenance more than ~6 months ago, or none on record | 15 |
| Scheduled maintenance overdue | 20 |

Floored at 0. Bands: **good** ≥ 80, **fair** ≥ 50, **poor** below. The API returns the deductions with the
score, so the UI can say *why* a machine is at 45.

## Documents and the AI assistant

```
upload (PDF/.txt/.md, ≤ 10 MB) ─▶ 202 Accepted ─▶ background: extract text per page
   ─▶ normalise typography ─▶ chunk (1,000 chars, 150 overlap) ─▶ extract codes (E-47 → E47)
   ─▶ embed (bge-small-en-v1.5, 384-d) ─▶ document_chunks

question ─▶ three searches in SQL, scoped to the machine (+ plant-wide documents)
              code     exact code overlap                 codes && :codes
              words    English full-text, any word         content_tsv @@ OR-query
              meaning  cosine similarity                   embedding <=> :vector
         ─▶ reciprocal rank fusion  Σ weight / (60 + rank)   (code weight 2)
         ─▶ relevance gate: a code match, every word present, or similarity ≥ 0.55; else "not covered"
         ─▶ top 5 chunks, numbered ─▶ LLM: answer ONLY from these, cite [n]
         ─▶ answer + sources (title, page, cited or not) + confidence
```

Why three channels: full-text search splits "E-47" into "e" and "47", so an exact code needs its own
channel; full-text catches exact words; embeddings catch paraphrases ("wobbles" ≈ "vibration"). Rank fusion
merges them without calibrating three different score scales.

`/ai/diagnose/{machine}` adds the machine's recent service history and open issues (and their error codes)
to the question before retrieval, so "spindle vibrates" also searches for the open issue's `E-47`.

**LLM providers.** Groq (`openai/gpt-oss-120b`) first, Gemini (`gemini-3.5-flash-lite`) on any failure, both
on free tiers, pinned model names, no retries (moving to the next provider beats retrying a rate-limited
one). With no provider available the API still answers with the matching manual excerpts. Each user may ask
30 questions an hour, so a public demo can't drain the free quotas.

**Embeddings run locally** (fastembed, ONNX on CPU): no API cost, no rate limit, and switching LLM provider
never forces re-embedding. The cost is memory (~500 MiB for the API), which shaped the hosting choice.

## Authentication

- `POST /auth/login` returns a JWT (HS256, 60 minutes) holding only the user id. Every request loads the
  user, so a deactivated account or changed role takes effect immediately, not when the token expires.
- Passwords are hashed with Argon2id. Accounts are created by an admin; there is no public sign-up.
- The browser never sees the token: the Next.js server stores it in an `httpOnly`, `Secure`, `SameSite=Lax`
  cookie and attaches it when it proxies `/api/v1/*` to the API. Injected scripts can't read it, and the API
  needs no CORS because the browser only talks to its own origin.

## Database migrations

Liquibase owns the schema; the application never creates tables. The changelog is versioned (`v1.0` to
`v1.5`, 32 changesets) and **release-safe**:

- An applied changeset is never edited. Fixes are new changesets (v1.1 fixes the drift found in v1.0).
- Changes are additive (expand/contract), so migrations run *before* the new code is deployed while the old
  code keeps working.
- Every changeset from v1.1 on can be rolled back: raw-SQL changes carry an explicit `<rollback>`, and
  `createIndex` changes are reversed by Liquibase automatically.
- The test suite runs the real changelog against a throwaway Postgres container, so a broken migration or a
  model that no longer matches the schema fails CI.

## Alternatives considered

| Choice | Picked | Over | Why |
|---|---|---|---|
| Vector store | pgvector in Postgres | Chroma, Pinecone | One database to run, back up and migrate; filters and joins in SQL. |
| Search | Hybrid (codes + full-text + vectors) | Vectors only | Error codes and part numbers need exact matching. |
| Background work | FastAPI `BackgroundTasks` + status columns | Celery + Redis | One process is enough at this scale; status on the row means nothing is lost. |
| LLM | Free Groq → Gemini chain | Paid API | Zero cost; the fallback chain and excerpt mode cover outages and rate limits. |
| Token storage | httpOnly cookie behind a server proxy | `localStorage` | Not readable by injected scripts; no CORS. |
| Hosting | Azure Container Apps + Neon + Vercel | Azure Postgres, Render | Free indefinitely, enough memory for local embeddings, no lock-in. See DEPLOYMENT.md. |
