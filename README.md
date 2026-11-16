# EquipTrack

**Maintenance management for a manufacturing plant, with an AI assistant that answers from the machine manuals and cites them.**
Track machines, service history, faults and spare parts; ask "what does E-47 mean on the lathe?" and get a
cited answer from the right manual.

**Live demo:** https://equip-track-lyart.vercel.app. Click a demo account on the sign-in page
(supervisor or technician, sample data only). The API scales to zero when idle, so the first visit after a quiet
spell wakes it (~25 s); the sign-in page starts that the moment it opens.

| | |
|---|---|
| Automated tests | **193 passing**, **98.61%** line coverage (CI gate: 95%) |
| AI retrieval (23-question eval) | hit@1 **100%**, hit@3 **100%** for answerable questions |
| AI answers (same eval, live LLM) | **23/23** correct or correctly refused; median LLM latency **828 ms** |
| Production | Vercel + Azure Container Apps + Neon Postgres; CI-gated continuous delivery; **$0/month** at demo traffic |
| Cold start / warm | **23-24 s** from zero / **~1 s** warm (`/health`) |

Stack: Python 3.12, FastAPI, SQLModel (async SQLAlchemy 2.1), Postgres 16 + pgvector, Liquibase, Pytest +
testcontainers, LangChain (Groq → Gemini), fastembed, Next.js 16 + React 19 + Tailwind 4 + shadcn/ui, Docker,
GitHub Actions, Azure Container Apps.

## How it works

```
Browser ──▶ Next.js on Vercel ──────▶ FastAPI on Azure Container Apps ──▶ Neon Postgres 16 + pgvector
            pages + server proxy        routers → services → models        tables, files, chunks
            (JWT in httpOnly cookie)    background indexing (fastembed)    (vector + full-text + codes)
                                        /ai/* → Groq → Gemini → excerpts
GitHub: push → CI (lint, 193 tests, Docker e2e, frontend build, API contract)
             → Deploy (image to GHCR → Liquibase on Neon → Azure rollout → /health smoke test)
```

**Why these choices**

- **One Postgres for everything.** Relational data, uploaded files, full-text indexes and embeddings
  (pgvector) share one database, one backup and one migration tool (Liquibase). No separate vector store to run.
- **Hybrid search, not just vectors.** Full-text search splits `E-47` into `e` and `47`, and embeddings blur
  exact codes, so retrieval runs three searches (exact codes, English full-text, cosine similarity) and merges
  them with reciprocal rank fusion. A relevance gate makes it say "the manuals don't cover this" instead of guessing.
- **Free, resilient AI.** Groq first, Gemini if it fails, matching manual excerpts if both are down. Embeddings
  run locally, so they cost nothing and never depend on an LLM provider. 30 questions per user per hour
  protects the free quotas.
- **Rules in a service layer.** The issue lifecycle (who may move an issue where), atomic stock changes and the
  explainable 0-100 health score are plain functions with their own tests, not logic buried in routes.
- **Release-safe migrations.** Applied changesets are never edited; fixes are new, additive changesets, so
  migrations can run before the new code ships. Tests run the real changelog against a real Postgres.
- **The token never reaches the browser's JavaScript.** Next.js keeps the JWT in an httpOnly cookie and proxies
  API calls server-side, so there's no CORS and nothing for an injected script to steal.

The full design (roles and permissions, data model, issue lifecycle, health score, RAG pipeline, auth,
alternatives considered) is in [docs/DESIGN.md](docs/DESIGN.md).

## Data

- **Demo plant** (`app/seed_demo.py`): 10 machines, 10 maintenance logs, 6 issues, 8 parts and 4 users, with
  dates relative to today so "due in 30 days" and "overdue" always mean something. Idempotent; it never changes
  an existing password.
- **Manuals** (`sample_data/manuals/`): four fictional manuals I wrote for this project (a CNC lathe, a
  stamping press, an air compressor and a plant-wide lockout/tagout procedure). They deliberately reuse a code
  (`E-47` means different things on the lathe and the press) to test that answers stay scoped to the right machine.
- **Eval set** (`evals/rag_cases.json`): 23 questions over those manuals: exact codes, lowercase codes,
  paraphrases, symptoms, numbers, and 3 that must be refused.

## Results

### Tests and quality gates (run 17 Nov 2026)

| Check | Result |
|---|---|
| `pytest` against Postgres + pgvector in Docker, migrated by the real Liquibase changelog | 193 passed |
| Line coverage | 98.61% (gate 95%) |
| `ruff` (backend), `eslint` + `tsc` + `next build` (frontend) | clean |
| API contract: OpenAPI export vs. the frontend's generated types | in sync |
| Login page, against the live API from cold | "waking" shown at once, ready after 23.1 s, 0 console errors |

### RAG evaluation ([reports/rag_eval.md](reports/rag_eval.md), 16 Nov 2026)

| Relevance threshold | hit@1 | hit@3 | refused correctly (retrieval only) |
|---|---|---|---|
| 0.50 | 100% | 100% | 1/3 |
| **0.55 (chosen)** | **100%** | **100%** | 1/3 |
| 0.60 | 95% | 95% | 2/3 |
| 0.70 | 70% | 70% | 2/3 |

With the LLM in the loop: **23/23** correct (22 answered by `openai/gpt-oss-120b` on Groq, 1 refused before any
LLM call), 20 of 22 answers cite a source, median latency 828 ms (max 1,525 ms). The two near-miss refusals
that retrieval let through were refused by the LLM, which is told to answer only from the excerpts.
I chose 0.55 because raising it to 0.60 starts losing real answers.

### Before vs. after

| | July 2026 (first build) | November 2026 (now) |
|---|---|---|
| Database routes | **every one returned 500** (`KeyError: 'DocumentTable'`) | all working |
| Fresh install | crashed (unpinned deps: no `greenlet`, naive datetimes rejected) | pinned; one-command Docker stack |
| `docker compose` | never connected (wrong URL scheme, no migrations, no healthcheck) | Postgres → Liquibase → API, health-checked |
| Behaviour vs. design | 16 of 28 checks passed (after the two crash fixes) | covered by 193 tests |
| Tests / CI / CD | 0 / none / none | 193 tests, 98.61% / 5 CI jobs / continuous delivery to Azure |
| Schema | model/database drift, 0 of 9 planned indexes, no rollbacks | 32 release-safe changesets (v1.0-v1.5), indexes, rollbacks |
| API | 23 routes, no auth | 46 operations, JWT + 3 roles |
| Features | CRUD only | analytics + health score, documents, hybrid RAG assistant |
| Frontend | none | Next.js app: 8 pages, light/dark, responsive, floating AI assistant |
| README | 1 line | this |

## Project structure

```
app/
  main.py                FastAPI app: routers, error handlers, /health
  dependencies.py        current user, role checks, AI rate limit, shared lookups
  create_admin.py        create the first admin (no public sign-up)
  seed_demo.py           idempotent demo plant + manuals
  core/                  settings (env), async engine + sessions, in-memory rate limiter
  models/                SQLModel tables: equipment, maintenance, issue, part, user, document (+ files, chunks)
  schemas/               request/response models and enums
  routers/               auth, equipment, maintenance, issues, parts, analytics, documents, ai
  services/              issue lifecycle, stock, health score, analytics, indexing, chunking,
                         embeddings, hybrid retrieval, LLM chain, ask/diagnose
migrations/              Liquibase: changelog.xml (v1.0) + changesets/ v1.1-v1.5
tests/                   pytest suite (testcontainers Postgres + real Liquibase)
evals/                   RAG eval: cases + runner
reports/                 generated eval results
sample_data/manuals/     the four fictional manuals
frontend/
  src/app/               pages: dashboard, equipment (+ detail), issues, maintenance, parts, documents, users, login
  src/app/api/           server routes: login/logout (cookie), backend proxy, warm-up
  src/components/        layout, dashboard, equipment, issues, maintenance, parts, documents, assistant, users, ui
  src/lib/               typed API client (generated from OpenAPI), queries, auth, formatting
docs/DESIGN.md           how it works and why
docs/DEPLOYMENT.md       hosting, CI/CD, cost guardrails, first-time setup
scripts/export_openapi.py   OpenAPI export for the frontend's generated types
.github/workflows/       ci.yml (lint, test, docker e2e, frontend, api-contract), deploy.yml (CD)
Dockerfile, docker-compose.yml, requirements.txt (runtime, pinned), requirements-dev.txt
```

## Run locally

Needs Docker and Node 24 (what CI uses).

```bash
cp .env.example .env            # optional: add GROQ_API_KEY / GEMINI_API_KEY for LLM answers
docker compose up --build       # Postgres :5433 -> Liquibase migrations -> API :8000 (hot reload)
docker compose exec app python -m app.seed_demo    # demo plant, users and manuals
```

```bash
cd frontend
cp .env.example .env.local      # API_URL=http://localhost:8000
npm ci && npm run dev           # http://localhost:3000
```

Sign in with a demo account (shown on the sign-in page; defined in `app/seed_demo.py`). Without LLM keys the
assistant still answers with the matching manual excerpts. API docs: http://localhost:8000/docs.

**Test** (Docker must be running; the suite starts its own Postgres):

```bash
pip install -r requirements-dev.txt
ruff check app tests evals
pytest --cov --cov-report=term --cov-fail-under=95
```

**Evaluate the RAG pipeline:**

```bash
python -m evals.rag_eval              # retrieval metrics + threshold sweep (no LLM calls)
python -m evals.rag_eval --with-llm   # also grade live answers (~23 LLM calls)
```

## Deployment

| Piece | Where |
|---|---|
| Frontend | Vercel (root directory `frontend/`, env `API_URL`) |
| API | Azure Container Apps, Consumption plan: 0.5 vCPU / 1 GiB, 0-1 replicas, image from public GHCR |
| Database | Neon Postgres 16 + pgvector (direct connection, TLS) |
| Delivery | `.github/workflows/deploy.yml`: after CI passes on `main`, build image → Liquibase on Neon → `az containerapp update` → `/health`. Azure login is OIDC, so no cloud password is stored. |

Python 3.12, Node 24, Liquibase 4.29, `pgvector/pgvector:pg16`; all Python dependencies pinned. Cost guardrails,
kill switch, rollback and the full first-time setup are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Limitations

- **Small, self-written eval.** 23 questions over 4 short fictional manuals I wrote myself. It shows the pipeline
  works and catches regressions; it doesn't prove quality on real, messy manuals.
- **Retrieval alone refuses only 1 of 3 off-topic questions** at the chosen threshold; the LLM catches the
  other two. Without an LLM (excerpt mode) those two would show loosely related excerpts.
- **Cold starts take 23-24 s** after a few idle minutes (a ~1 GB image plus the embedding model). The sign-in
  page hides most of it, but a deep link opened cold still waits.
- **The rate limiter is in memory**: correct with one replica, reset on restart, not shared across replicas.
- **Scanned PDFs** (no text layer) can't be indexed; there's no OCR. The document shows the error instead.
- **No password reset or email**: accounts are created by an admin. Tokens last 60 minutes with no refresh.
- **The public demo is shared**: anyone with the supervisor login can change statuses, assign issues and
  restock parts. Re-running the seed restores missing demo data; admin actions use a private password.
- **Not load-tested.** Single region, one replica, free tiers throughout.

## Learning log: mistakes and what I learned

Built in layers: a fast first build in July 2026, then a rebuild in November that made it work and took it to
production. Each layer records what went wrong and the lesson.

### Layer 1 - The first build (20-30 July 2026, FastAPI, SQLModel, Liquibase, Docker)

*What I built:* A FastAPI + async SQLModel API over Postgres with Liquibase migrations: equipment, maintenance
logs, issues, parts and documents, 23 routes in a layered `app/` package, written over about a week after a
one-table warm-up API.

| # | Mistake | What actually happened | Lesson |
|---|---|---|---|
| 1.1 | **Referenced a model nothing imported** | Commit `2c1d681` added `documents: List["DocumentTable"]` to `EquipmentTable`, but nothing imported `DocumentTable`. SQLAlchemy couldn't build its mappers (`KeyError: 'DocumentTable'`), so every database route returned 500. | Start the app and hit one route after every commit; one smoke test would have caught it the same day. |
| 1.2 | **Unpinned dependencies** | A fresh install months later pulled SQLAlchemy 2.1 (no longer installs `greenlet`, so the app wouldn't import) and SQLModel 0.0.50 (rejects naive `datetime.now()`). The file also listed packages the code never used. | Pin everything that runs in production; "it worked when I wrote it" isn't a version. |
| 1.3 | **The documented way to run it had never worked** | `docker compose` used `postgresql://`, which the async engine can't use (`postgresql+asyncpg://`). It had no Liquibase service, no healthcheck, and port 5432 clashed with a local Postgres. Running uvicorn by hand worked only because my local `.env` had the right URL. | The path in the README must be the path you actually test. |
| 1.4 | **Models and the database drifted apart** | `equipment.department` defaulted to `'active'`; `documents.uploaded_by` was NOT NULL with default `'false'` and missing from the model; `documents.equipment_id` was NOT NULL but its foreign key said `ON DELETE SET NULL`; `performed_at` was a timestamp in the database and a date in the schema; 0 of the 9 indexes I'd planned existed; no changeset had a rollback. | The schema is a contract. Test the code against the real migrated database, and fix mistakes with new changesets, never by editing applied ones. |
| 1.5 | **Behaviour I never checked** | With the crashes fixed, 16 of 28 design checks passed: empty lists returned 404 instead of `[]`; an issue could jump Open → Closed, and a leftover shortcut let Closed go back only to Open; a bad equipment id gave a 500; hard delete gave a 500 (SQLAlchemy tried to null the children instead of letting Postgres cascade); stock of 0 was rejected; search was case-sensitive; `updated_at` never changed. | Write the rules down as tests. Status-code and edge-case behaviour is the API's real contract. |
| 1.6 | **Left half-finished work in the working tree** | Uncommitted auth work had `type="UUID"n` in the changelog (invalid XML), a syntax error in the AI router, and a circular import between the user and issue models. | Commit small, working steps or use a branch; a half-done change sitting in the tree blocks everything else. |
| 1.7 | **Didn't carry over what already worked** | My warm-up API already ran Liquibase inside compose and tested against real Postgres with testcontainers. EquipTrack had neither, and had 0 tests. | Reuse your own proven patterns; the second project should start where the first one ended. |
| 1.8 | **Personal planning notes in a public repo** | A long planning document with personal notes was committed to the public repo. Deleting it later doesn't remove it from git history. | Decide what is public before the first push; keep private notes out of the repository. |

### Layer 2 - The rebuild: make it work, then build it out (16 November 2026, Claude Code)

*What I did:* Fixed the root causes one commit at a time, put tests and CI under everything, then added
auth, analytics, document indexing, a hybrid RAG assistant with an eval, and a Next.js frontend.

| # | Decision | Why |
|---|---|---|
| 2.1 | Smallest-diff hotfix first: import the model, pin every dependency, UTC-aware timestamps | Ship the repair before any refactor (fixes 1.1, 1.2). |
| 2.2 | Health-checked compose: Postgres → Liquibase → API, host port 5433, `.env.example` | The documented path becomes the tested path (1.3). |
| 2.3 | New v1.1 and v1.2 changesets for the drift and the indexes; v1.0 left untouched | Release-safe migrations: never edit what's been applied (1.4). |
| 2.4 | A services layer for the issue lifecycle and atomic stock updates; consistent 200/404/409/422 | Rules testable on their own; no race on the last spare part (1.5). |
| 2.5 | JWT auth, Argon2id, three roles, additive user-id columns instead of the destructive draft migration | Auth was required, and it had to arrive without breaking existing rows (1.6). |
| 2.6 | Pytest against a testcontainers Postgres migrated by the real Liquibase changelog; 95% coverage gate in CI | A broken migration or drifted model fails CI, not production (1.4, 1.7). |
| 2.7 | pgvector in the same Postgres, local embeddings, hybrid retrieval with rank fusion, a relevance gate, a 23-case eval with a threshold sweep | Codes like `E-47` need exact matching; the threshold is picked from data, not guessed. |
| 2.8 | Free LLM chain (Groq → Gemini → excerpts) with pinned model names | Zero cost, and an outage degrades the answer instead of breaking it. |
| 2.9 | Next.js with an httpOnly-cookie proxy and API types generated from OpenAPI, checked in CI | The token stays out of JavaScript; a backend change that breaks the frontend's types fails the build. |

**What went wrong along the way**

| # | Mistake | What actually happened | Lesson |
|---|---|---|---|
| 2.10 | **Hid a failing gate behind `tail -1`** | I piped the coverage-gated test run through `tail -1`, saw a passing line and called it 99%. CI went red: coverage was 93.62% because the new seed script had no tests. | Never trim the output of a check that can fail; read the exit code and the coverage lines. |
| 2.11 | **Assumed full-text search keeps codes whole** | Postgres splits `E-47` into `e` and `47`, so exact error-code questions ranked poorly. | Test the tokenizer on your real identifiers; that's why there's a separate code channel. |
| 2.12 | **Trusted the ORM's insert order** | SQLAlchemy orders INSERTs by `relationship()` links, not bare foreign keys, so it sometimes wrote a file row before its document. | Flush the parent explicitly when the link isn't a relationship. |
| 2.13 | **Rendered time and role on the server** | `new Date()` and role-dependent markup differed between server and browser: hydration errors, and a build failure under Next 16's prerender rules. | Anything that depends on the clock or the signed-in user renders after hydration. |
| 2.14 | **A test used the laptop's date** | The "upcoming in 30 days" test used local `date.today()` while the API uses UTC, so it failed every night between 00:00 and 05:30 IST and passed in CI. | Tests must use the same clock as the code. |

### Layer 3 - Shipping it (17 November 2026, Azure Container Apps, Neon, Vercel, GitHub Actions)

*What I did:* Hardened the API for a public demo, added continuous delivery, and deployed it for $0 a month.

| # | Decision | Why |
|---|---|---|
| 3.1 | Azure Container Apps for the API, not a 512 MB free host | Local embeddings need ~500 MiB; Container Apps lets me set 1 GiB and scales to zero inside a monthly grant that doesn't expire. |
| 3.2 | Neon for Postgres, GHCR for the image | Free with no expiry (Azure's free Postgres lasts 12 months; its registry costs ~$5/month), and the database isn't tied to the API's host. |
| 3.3 | Deploy only after CI passes, migrations before the rollout, then a `/health` smoke test | Nothing untested ships; additive migrations make the order safe. |
| 3.4 | OIDC from GitHub to Azure, scoped to one resource group | No cloud password stored anywhere. |
| 3.5 | Accept the host's database URL as given (`sslmode` → `ssl`, drop `channel_binding`) | asyncpg rejects libpq-style options; paste-and-go config avoids a production-only crash. |
| 3.6 | 30 AI questions per user per hour; a private admin password via `DEMO_ADMIN_PASSWORD` | A public demo must not drain free LLM quotas or hand out admin rights. |
| 3.7 | Max 1 replica, no log ingestion, a budget alert, a documented kill switch | Pay-as-you-go with no trial credit needs guardrails from day one. |
| 3.8 | The sign-in page wakes the API and shows its status; one-click demo accounts | Turns a silent 24 s wait into one that overlaps with reading the page. |

**What went wrong along the way**

| # | Mistake | What actually happened | Lesson |
|---|---|---|---|
| 3.9 | **Planned on a free tier that had changed** | The first hosting plan used Hugging Face Docker Spaces; their docs now require a paid plan for Docker. | Check current pricing pages before planning around a free tier. |
| 3.10 | **Configured OIDC with the old subject format** | Azure refused the login (`AADSTS700213`): GitHub sent `repo:Owner@<id>/Repo@<id>:environment:production`, with numeric IDs, not just names. | Copy the exact claim from the failing log; IDs can't be renamed or reused, which is why GitHub sends them. |
| 3.11 | **Documented a kill switch that doesn't exist** | I wrote `--max-replicas 0`; Container Apps requires at least 1. The real off switch is disabling ingress. | Check limits in the docs before writing an emergency procedure. |
| 3.12 | **Seed command for the wrong CPU** | The documented seed used the amd64 GHCR image, which would need emulation on an Apple Silicon Mac. | Run one-off jobs with an image built for the machine that runs them. |

*Known gaps I chose not to fix:* a larger eval on real manuals, OCR for scanned PDFs, password reset, a shared
rate limiter for multiple replicas, a smaller image for faster cold starts.

### Key takeaways

1. **Run it the way it really runs.** Every Layer 1 failure was invisible from the editor and obvious the first time someone ran the documented command.
2. **Make the schema a tested contract.** Real migrations in the test database turned silent drift into failing builds.
3. **Never trust a green line you trimmed.** Read the exit code and the numbers a gate is checking.
4. **Exact identifiers need exact search.** Hybrid retrieval beat pure vectors the moment error codes showed up.
5. **Free hosting is an architecture constraint.** Memory limits, cold starts and expiring offers decided the design as much as the code did.

## Future improvements

- A bigger eval with real (public) equipment manuals, and answer grading beyond fact matching.
- A smaller image (CPU-only wheels, multi-stage build) to cut the cold start.
- OCR for scanned PDFs; streaming answers in the assistant.
- Redis-backed rate limiting if the API ever runs more than one replica.
