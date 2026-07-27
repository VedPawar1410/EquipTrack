# EquipTrack — Manufacturing Equipment Maintenance System
### Capstone Project Specification | Full Backend Deep-Dive

---

## 1. The Real Problem

Every manufacturing plant — from automotive floors to electronics factories — runs on physical equipment: CNC machines, conveyor belts, welding robots, hydraulic presses, measurement tools. When a machine breaks down unexpectedly, the entire production line can stop. The industry term for this is **unplanned downtime**, and it costs manufacturers an average of $260,000 per hour.

The root cause, almost universally, is the same: maintenance is still managed in Excel sheets, paper logs, and the memory of experienced technicians. When a machine throws error code E-47, the maintenance engineer searches through a printed manual. When a bearing needs replacement every 6 months, the reminder is a sticky note. When a critical machine retires, its maintenance history walks out the door with the employee who managed it.

This is exactly the problem that GM's Manufacturing Intelligent Ecosystem project is trying to solve — modernizing these ad-hoc tools into structured web applications with AI layered on top.

**EquipTrack** is a web-based equipment maintenance management system that replaces Excel spreadsheets and paper logs with a structured API. Maintenance crews log work orders, track machine health, report issues with severity levels, manage spare parts inventory, and ask AI questions about their machines using a RAG pipeline over the equipment manuals.

---

## 2. What This Project Teaches You

Every single thing in this project maps directly to the GM job description:

| Project feature | JD requirement it demonstrates |
|---|---|
| FastAPI routers, Pydantic models | "FastAPI or similar modern API framework" |
| PostgreSQL schema with relationships | "Solid SQL and PostgreSQL knowledge" |
| Liquibase XML changesets | "Schema migrations and release-safe DB changes" |
| Pytest route + DB tests | "Automated tests with Pytest" |
| `docker-compose.yml` with app + DB | "Dockerized local development" |
| Azure Container Apps deployment | "Azure deployment skills" |
| LangChain RAG endpoint | "RAG system, LangChain, AI/ML skills (nice-to-have)" |
| OpenAPI docs at `/docs` | "REST APIs, OpenAPI standard" |
| Clean router/service/model separation | "Simple, reliable, easy to deploy backend" |

---

## 3. Architecture Overview

```
Next.js client (frontend — vibe-code this last)
         │  HTTP / JSON
         ▼
┌─────────────────────────────────────────────────┐
│           FastAPI Backend — Python 3.12         │
│  ┌──────────┐ ┌────────────┐ ┌────────┐ ┌────┐ │
│  │Equipment │ │Maintenance │ │ Issues │ │ AI │ │
│  └──────────┘ └────────────┘ └────────┘ └────┘ │
│          SQLModel ORM · Pydantic schemas         │
└───────────────────┬──────────────────┬──────────┘
                    │                  │
          ┌─────────▼──────┐  ┌────────▼──────────┐
          │  PostgreSQL 16  │  │  LangChain RAG    │
          │  5 tables       │  │  Azure OpenAI     │
          │  Liquibase      │  │  ChromaDB (local) │
          └─────────────────┘  └───────────────────┘
                    │
        ┌───────────▼───────────────────────────┐
        │  Docker Compose (local development)   │
        │  Azure Container Apps (production)    │
        │  Azure DB for PostgreSQL              │
        │  Azure Blob Storage (PDF manuals)     │
        └───────────────────────────────────────┘
```

---

## 4. Database Schema

Five tables. Every column has a reason.

---

### Table: `equipment`

The central entity. Everything else references this.

```sql
CREATE TABLE equipment (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    model_number    VARCHAR(50),
    serial_number   VARCHAR(100) UNIQUE,
    equipment_type  VARCHAR(50) NOT NULL,   -- 'CNC_MACHINE', 'CONVEYOR', 'PRESS', 'WELDING_ROBOT', 'MEASURING'
    location        VARCHAR(100) NOT NULL,   -- 'Floor A, Bay 3'
    department      VARCHAR(100) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active', 'under_maintenance', 'retired'
    purchased_at    DATE,
    warranty_expires_at DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);
```

**Why these design choices:**
- `UUID` over `SERIAL INT`: avoids sequential guessability, safe for distributed systems later
- `TIMESTAMPTZ` not `TIMESTAMP`: always stores timezone-aware timestamps — critical in manufacturing where shifts span timezones
- `status` as `VARCHAR` not an enum: Postgres enums require a migration to add values; VARCHAR is more flexible
- `serial_number UNIQUE`: enforces that the same physical machine can't be registered twice

---

### Table: `maintenance_logs`

Records every maintenance event performed on a machine. This becomes the machine's health history.

```sql
CREATE TABLE maintenance_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id     UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    log_type         VARCHAR(30) NOT NULL,  -- 'scheduled', 'emergency', 'inspection', 'calibration'
    performed_by     VARCHAR(100) NOT NULL,
    performed_at     TIMESTAMPTZ NOT NULL,
    description      TEXT NOT NULL,
    duration_minutes INT CHECK (duration_minutes > 0),
    cost_usd         NUMERIC(10,2),
    next_scheduled_at TIMESTAMPTZ,          -- when to schedule the next maintenance
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Why these design choices:**
- `ON DELETE CASCADE`: if a machine is deleted, its maintenance history goes with it (makes sense — orphaned logs are meaningless)
- `CHECK (duration_minutes > 0)`: database-level validation, not just API-level
- `NUMERIC(10,2)` not `FLOAT` for cost: floating-point is unreliable for money; NUMERIC is exact

---

### Table: `issues`

Issues reported about equipment — anything from minor quirks to critical failures.

```sql
CREATE TABLE issues (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id   UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    title          VARCHAR(200) NOT NULL,
    description    TEXT,
    severity       VARCHAR(20) NOT NULL,   -- 'low', 'medium', 'high', 'critical'
    status         VARCHAR(20) NOT NULL DEFAULT 'open',  -- 'open', 'in_progress', 'resolved', 'closed'
    reported_by    VARCHAR(100) NOT NULL,
    assigned_to    VARCHAR(100),           -- nullable until assigned
    error_code     VARCHAR(50),            -- machine error code, e.g. 'E-47' (used by RAG)
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ            -- nullable until resolved
);
```

**Why `error_code` exists:** This column is the bridge to the AI system. When maintenance logs an issue with error code "E-47", the RAG endpoint can look up that code in the equipment manual and return a diagnosis. This makes the AI feature feel organic, not bolted on.

---

### Table: `parts`

Spare parts inventory for each machine. Tracks stock levels and reorder thresholds.

```sql
CREATE TABLE parts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id        UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    part_name           VARCHAR(100) NOT NULL,
    part_number         VARCHAR(100),
    quantity_in_stock   INT NOT NULL DEFAULT 0 CHECK (quantity_in_stock >= 0),
    reorder_threshold   INT NOT NULL DEFAULT 2,
    unit_cost_usd       NUMERIC(10,2),
    supplier            VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);
```

---

### Table: `documents`

Uploaded equipment manuals and SOPs. These get embedded into the vector store for RAG.

```sql
CREATE TABLE documents (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id     UUID REFERENCES equipment(id) ON DELETE SET NULL,  -- nullable (some docs are general)
    title            VARCHAR(200) NOT NULL,
    blob_url         TEXT NOT NULL,   -- Azure Blob Storage URL
    doc_type         VARCHAR(50) NOT NULL,  -- 'manual', 'sop', 'safety_guide', 'datasheet'
    file_size_bytes  INT,
    is_indexed       BOOLEAN NOT NULL DEFAULT FALSE,  -- FALSE until embedded into vector store
    uploaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Why `is_indexed`:** Embedding a PDF into a vector store takes a few seconds. Rather than doing it synchronously during the upload request (which would time out for large PDFs), you upload → store metadata → set `is_indexed=FALSE` → a background task processes it later → sets `is_indexed=TRUE`. This is a real-world async pattern.

---

### Table relationships

```
equipment (1) ─────── (many) maintenance_logs
equipment (1) ─────── (many) issues
equipment (1) ─────── (many) parts
equipment (1) ─────── (many) documents
```

---

### Indexes to add

```sql
CREATE INDEX idx_equipment_status     ON equipment(status);
CREATE INDEX idx_equipment_department ON equipment(department);
CREATE INDEX idx_issues_status        ON issues(status);
CREATE INDEX idx_issues_severity      ON issues(severity);
CREATE INDEX idx_issues_equipment_id  ON issues(equipment_id);
CREATE INDEX idx_maintenance_equip_id ON maintenance_logs(equipment_id);
CREATE INDEX idx_parts_equipment_id   ON parts(equipment_id);
CREATE INDEX idx_documents_equip_id   ON documents(equipment_id);
CREATE INDEX idx_parts_low_stock      ON parts(quantity_in_stock) WHERE quantity_in_stock <= reorder_threshold;
```

The partial index on `parts` (`WHERE quantity_in_stock <= reorder_threshold`) is particularly efficient — the "low stock alert" query will only scan rows that actually need attention.

---

## 5. API Endpoints (All Routes)

Base path: `/api/v1`
All responses are JSON. All errors follow the same shape: `{"detail": "error message"}`.

---

### Equipment Router (`/api/v1/equipment`)

| Method | Path | Description | Status codes |
|---|---|---|---|
| POST | `/equipment` | Create a new equipment record | 201, 422 |
| GET | `/equipment` | List all equipment (filterable) | 200 |
| GET | `/equipment/{id}` | Get single equipment by ID | 200, 404 |
| GET | `/equipment/{id}/summary` | Full snapshot: equipment + last 5 logs + open issues + parts | 200, 404 |
| PUT | `/equipment/{id}` | Full update of an equipment record | 200, 404, 422 |
| PATCH | `/equipment/{id}/status` | Update status only (active/under_maintenance/retired) | 200, 404 |
| DELETE | `/equipment/{id}` | Soft-delete by setting status=retired | 204, 404 |

**Query params for GET /equipment:**
- `?status=active` — filter by status
- `?department=Assembly` — filter by department
- `?type=CNC_MACHINE` — filter by type
- `?search=Robot` — partial name search

**POST /equipment request body:**
```json
{
  "name": "CNC Lathe A3",
  "model_number": "HAAS-ST-30",
  "serial_number": "SN-20231104-A3",
  "equipment_type": "CNC_MACHINE",
  "location": "Floor A, Bay 3",
  "department": "Machining",
  "purchased_at": "2022-03-15",
  "warranty_expires_at": "2025-03-15"
}
```

**POST /equipment response (201):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "CNC Lathe A3",
  "model_number": "HAAS-ST-30",
  "serial_number": "SN-20231104-A3",
  "equipment_type": "CNC_MACHINE",
  "location": "Floor A, Bay 3",
  "department": "Machining",
  "status": "active",
  "purchased_at": "2022-03-15",
  "warranty_expires_at": "2025-03-15",
  "created_at": "2024-11-04T09:30:00Z"
}
```

---

### Maintenance Router (`/api/v1/maintenance`)

| Method | Path | Description | Status codes |
|---|---|---|---|
| POST | `/equipment/{id}/maintenance` | Log a maintenance event | 201, 404, 422 |
| GET | `/equipment/{id}/maintenance` | Get all logs for an equipment | 200, 404 |
| GET | `/maintenance/{log_id}` | Get a specific log | 200, 404 |
| GET | `/maintenance/upcoming` | All equipment with `next_scheduled_at` in next 30 days | 200 |

**POST /equipment/{id}/maintenance request body:**
```json
{
  "log_type": "scheduled",
  "performed_by": "Ravi Kumar",
  "performed_at": "2024-11-04T10:00:00Z",
  "description": "Full lubrication service. Replaced worn belt drive. Calibrated spindle.",
  "duration_minutes": 120,
  "cost_usd": 450.00,
  "next_scheduled_at": "2025-05-04T10:00:00Z"
}
```

---

### Issues Router (`/api/v1/issues`)

| Method | Path | Description | Status codes |
|---|---|---|---|
| POST | `/issues` | Report a new issue | 201, 422 |
| GET | `/issues` | List issues (filterable) | 200 |
| GET | `/issues/{id}` | Get a specific issue | 200, 404 |
| PATCH | `/issues/{id}/status` | Transition status | 200, 404, 422 |
| PATCH | `/issues/{id}/assign` | Assign to a technician | 200, 404 |
| GET | `/issues/critical` | All open critical issues (dashboard endpoint) | 200 |

**Query params for GET /issues:**
- `?status=open`
- `?severity=critical`
- `?equipment_id=<uuid>`
- `?assigned_to=Ravi`

**POST /issues request body:**
```json
{
  "equipment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Spindle vibration at high RPM",
  "description": "Machine shows error code E-47 and unusual vibration above 3000 RPM",
  "severity": "high",
  "reported_by": "Floor Supervisor Singh",
  "error_code": "E-47"
}
```

**PATCH /issues/{id}/status request body:**
```json
{ "status": "in_progress" }
```

**Valid status transitions:**
- `open` → `in_progress`
- `in_progress` → `resolved`
- `resolved` → `closed`
- `resolved` → `in_progress` (re-opened if fix didn't hold)

Enforce these transitions in your service layer, not just in the database. Invalid transitions return 422 with a clear message: `"Cannot transition from 'closed' to 'in_progress'"`.

---

### Parts Router (`/api/v1/parts`)

| Method | Path | Description | Status codes |
|---|---|---|---|
| POST | `/equipment/{id}/parts` | Add a part to equipment | 201, 404 |
| GET | `/equipment/{id}/parts` | List all parts for equipment | 200, 404 |
| GET | `/parts/{id}` | Get a specific part | 200, 404 |
| PATCH | `/parts/{id}/quantity` | Update stock quantity (add or subtract) | 200, 404, 422 |
| GET | `/parts/low-stock` | All parts at or below reorder threshold | 200 |

**PATCH /parts/{id}/quantity request body:**
```json
{ "quantity_change": -2 }   /* negative = consumed, positive = restocked */
```

---

### AI Router (`/api/v1/ai`)

| Method | Path | Description | Status codes |
|---|---|---|---|
| POST | `/ai/ask` | Ask a free-form question about any equipment | 200 |
| POST | `/ai/diagnose/{equipment_id}` | Describe a symptom, get AI diagnosis with equipment context | 200, 404 |
| POST | `/documents/upload` | Upload a PDF manual (store in blob, queue for embedding) | 202, 422 |

**POST /ai/ask request body:**
```json
{
  "question": "What does error code E-47 mean on the CNC Lathe A3?",
  "equipment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"  /* optional context */
}
```

**POST /ai/ask response:**
```json
{
  "answer": "Error code E-47 on the HAAS ST-30 series indicates a spindle encoder fault. This typically occurs due to a loose encoder cable connection or contamination on the encoder disc. Recommended action: 1) Power cycle the machine 2) Check encoder cable at rear of spindle 3) If persists, clean encoder disc with isopropyl alcohol. If unresolved after these steps, contact HAAS service.",
  "sources": ["HAAS_ST30_Maintenance_Manual.pdf, p.87", "HAAS_Error_Codes_Reference.pdf, p.23"],
  "confidence": "high"
}
```

**POST /ai/diagnose/{equipment_id} request body:**
```json
{
  "symptom": "High-pitched whining sound, error code E-47, vibration above 3000 RPM"
}
```

The diagnose endpoint is more powerful than `/ask`: it automatically pulls the machine's full profile, recent maintenance history, open issues, and relevant manual sections, then sends all of this as context to the LLM.

---

### Analytics Router (`/api/v1/analytics`) — bonus, build last

| Method | Path | Description |
|---|---|---|
| GET | `/analytics/dashboard` | Counts of equipment by status, issues by severity, upcoming maintenance count |
| GET | `/analytics/equipment/{id}/health` | Health score (0–100) based on open issues + maintenance frequency |

**Health score formula (implement in Python, not SQL):**
- Start at 100
- Subtract 10 for each open issue (severity=medium)
- Subtract 20 for each open issue (severity=high)
- Subtract 35 for each open issue (severity=critical)
- Subtract 15 if last maintenance was >6 months ago
- Subtract 20 if `next_scheduled_at` is in the past (overdue)
- Floor at 0

---

## 6. Liquibase Migration Plan

This is where you demonstrate release-safe database evolution. Each changeset gets its own file.

**Master changelog (`migrations/changelog.xml`):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
  xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
    http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.9.xsd">

  <include file="changesets/v1.0-create-equipment.xml"/>
  <include file="changesets/v1.1-create-maintenance-logs.xml"/>
  <include file="changesets/v1.2-create-issues.xml"/>
  <include file="changesets/v1.3-create-parts.xml"/>
  <include file="changesets/v1.4-create-documents.xml"/>
  <include file="changesets/v1.5-add-indexes.xml"/>
  <include file="changesets/v1.6-add-error-code-to-issues.xml"/>

</databaseChangeLog>
```

**Example changeset — `v1.0-create-equipment.xml`:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog">
  <changeSet id="1.0" author="your-name">
    <createTable tableName="equipment">
      <column name="id" type="UUID" defaultValueComputed="gen_random_uuid()">
        <constraints primaryKey="true" nullable="false"/>
      </column>
      <column name="name" type="VARCHAR(100)">
        <constraints nullable="false"/>
      </column>
      <column name="model_number" type="VARCHAR(50)"/>
      <column name="serial_number" type="VARCHAR(100)">
        <constraints unique="true"/>
      </column>
      <column name="equipment_type" type="VARCHAR(50)">
        <constraints nullable="false"/>
      </column>
      <column name="location" type="VARCHAR(100)">
        <constraints nullable="false"/>
      </column>
      <column name="department" type="VARCHAR(100)">
        <constraints nullable="false"/>
      </column>
      <column name="status" type="VARCHAR(20)" defaultValue="active">
        <constraints nullable="false"/>
      </column>
      <column name="purchased_at" type="DATE"/>
      <column name="warranty_expires_at" type="DATE"/>
      <column name="created_at" type="TIMESTAMPTZ" defaultValueComputed="NOW()">
        <constraints nullable="false"/>
      </column>
      <column name="updated_at" type="TIMESTAMPTZ"/>
    </createTable>

    <rollback>
      <dropTable tableName="equipment"/>
    </rollback>
  </changeSet>
</databaseChangeLog>
```

**Example of an additive (release-safe) changeset — `v1.6-add-error-code-to-issues.xml`:**
```xml
<changeSet id="1.6" author="your-name">
  <addColumn tableName="issues">
    <column name="error_code" type="VARCHAR(50)"/>
  </addColumn>
  <!-- No rollback needed: addColumn is already reversible in Liquibase -->
</changeSet>
```

**What makes a migration "release-safe":**
- **Safe:** `addColumn` (add new nullable column) — old app code ignores the new column
- **Safe:** `createIndex` — only affects performance, no data change
- **Safe:** `createTable` — new table, old code doesn't reference it
- **Unsafe:** `dropColumn` — old app code still tries to write to it → runtime error
- **Unsafe:** `renameColumn` — old code references old name → error
- **Unsafe:** adding NOT NULL to an existing column without a default → fails on existing null rows
- **Unsafe:** `modifyDataType` on a column with existing data — may corrupt data

In your interview, this is what they mean by "release-safe database changes." Know this cold.

---

## 7. Project Folder Structure

```
equiptrack/
├── app/
│   ├── main.py                   ← FastAPI app instantiation, router includes
│   ├── core/
│   │   ├── config.py             ← pydantic-settings: DB_URL, OPENAI_API_KEY, etc.
│   │   └── database.py           ← async engine, AsyncSession, get_db() dependency
│   ├── models/                   ← SQLModel table classes (ORM layer)
│   │   ├── equipment.py
│   │   ├── maintenance.py
│   │   ├── issue.py
│   │   ├── part.py
│   │   └── document.py
│   ├── schemas/                  ← Pydantic request/response classes (API layer)
│   │   ├── equipment.py          ← EquipmentCreate, EquipmentUpdate, EquipmentResponse
│   │   ├── maintenance.py
│   │   ├── issue.py
│   │   ├── part.py
│   │   └── ai.py
│   ├── routers/                  ← FastAPI route handlers (thin layer, no business logic)
│   │   ├── equipment.py
│   │   ├── maintenance.py
│   │   ├── issues.py
│   │   ├── parts.py
│   │   ├── ai.py
│   │   └── analytics.py
│   ├── services/                 ← Business logic lives here, NOT in routers
│   │   ├── equipment_service.py
│   │   ├── issue_service.py      ← status transition validation goes here
│   │   ├── parts_service.py      ← low-stock logic goes here
│   │   └── ai_service.py         ← LangChain RAG pipeline
│   └── dependencies.py           ← shared FastAPI Depends() functions
├── migrations/
│   ├── changelog.xml             ← Liquibase master file
│   └── changesets/
│       ├── v1.0-create-equipment.xml
│       ├── v1.1-create-maintenance-logs.xml
│       ├── v1.2-create-issues.xml
│       ├── v1.3-create-parts.xml
│       ├── v1.4-create-documents.xml
│       ├── v1.5-add-indexes.xml
│       └── v1.6-add-error-code-to-issues.xml
├── tests/
│   ├── conftest.py               ← shared fixtures: test DB, TestClient
│   ├── test_equipment.py
│   ├── test_maintenance.py
│   ├── test_issues.py
│   ├── test_parts.py
│   └── test_ai.py
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml       ← production override
├── .env.example
├── requirements.txt
└── README.md
```

**The key architectural decision — separating routers from services:**

Routers handle HTTP: they parse the request, call the service, and format the response. They contain no `if/else` business logic. Services contain all the decisions: "can this status transition happen?", "is there enough stock?", "what context does the AI need?". This separation means your business logic is testable without HTTP, and your routes stay thin and readable.

---

## 8. Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`requirements.txt`:**
```
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
sqlmodel>=0.0.19
asyncpg>=0.29.0
pydantic-settings>=2.3.0
python-multipart>=0.0.9
httpx>=0.27.0
pytest>=8.2.0
pytest-asyncio>=0.23.0

# AI/RAG (install these when you build the AI feature)
langchain>=0.2.0
langchain-openai>=0.1.0
langchain-community>=0.2.0
chromadb>=0.5.0
pypdf>=4.2.0
openai>=1.35.0
```

---

## 9. Docker Compose

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://equiptrack:password@db:5432/equiptrack_db
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      AZURE_OPENAI_ENDPOINT: ${AZURE_OPENAI_ENDPOINT}
      ENVIRONMENT: development
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - .:/app            # hot reload in dev
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: equiptrack
      POSTGRES_PASSWORD: password
      POSTGRES_DB: equiptrack_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U equiptrack -d equiptrack_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8001"
    volumes:
      - chroma_data:/chroma/chroma

volumes:
  postgres_data:
  chroma_data:
```

**`.env.example`:**
```
DATABASE_URL=postgresql+asyncpg://equiptrack:password@db:5432/equiptrack_db
OPENAI_API_KEY=sk-...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=...
AZURE_BLOB_CONNECTION_STRING=...
ENVIRONMENT=development
```

---

## 10. Pytest Strategy

The key challenge in testing FastAPI + async PostgreSQL: you need a separate test database that gets created fresh for each test run, and the session dependency needs to be overridden to use it.

**`tests/conftest.py`:**
```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import get_db

TEST_DATABASE_URL = "postgresql+asyncpg://equiptrack:password@localhost:5432/equiptrack_test"

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine):
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()   # rollback after every test — clean slate

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

**`tests/test_equipment.py` (sample tests):**
```python
import pytest

@pytest.mark.asyncio
async def test_create_equipment_success(client):
    payload = {
        "name": "CNC Lathe A3",
        "equipment_type": "CNC_MACHINE",
        "location": "Floor A, Bay 3",
        "department": "Machining"
    }
    response = await client.post("/api/v1/equipment", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "CNC Lathe A3"
    assert data["status"] == "active"
    assert "id" in data

@pytest.mark.asyncio
async def test_create_equipment_missing_required_field(client):
    payload = {"name": "CNC Lathe A3"}   # missing equipment_type, location, department
    response = await client.post("/api/v1/equipment", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_get_equipment_not_found(client):
    response = await client.get("/api/v1/equipment/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_list_equipment_filter_by_status(client):
    # Create two pieces of equipment, one active, one retired
    # ... (setup) ...
    response = await client.get("/api/v1/equipment?status=active")
    assert response.status_code == 200
    assert all(e["status"] == "active" for e in response.json())

@pytest.mark.asyncio
async def test_duplicate_serial_number_rejected(client):
    payload = {
        "name": "Machine 1",
        "serial_number": "SN-12345",
        "equipment_type": "PRESS",
        "location": "Floor B",
        "department": "Pressing"
    }
    await client.post("/api/v1/equipment", json=payload)
    response = await client.post("/api/v1/equipment", json=payload)  # same serial number
    assert response.status_code in (409, 422)

@pytest.mark.asyncio
async def test_issue_status_invalid_transition(client):
    # Create equipment, create issue, try to jump from 'open' to 'closed' directly
    # ... setup ...
    response = await client.patch(f"/api/v1/issues/{issue_id}/status", json={"status": "closed"})
    assert response.status_code == 422
```

**What to test per module:**
- Equipment: create (happy path), create (missing field → 422), get (404), list (filter works), duplicate serial (409)
- Maintenance: create log (happy path), get upcoming (returns correct items), get for non-existent equipment (404)
- Issues: create, status transitions (valid and invalid), filter by severity + status
- Parts: create, quantity update (add, subtract, subtract below zero → 422), low-stock filter
- AI: mock the LangChain call (don't actually hit the API in tests), test request/response shape

---

## 11. AI/RAG Component Design

The `/ai/ask` endpoint is the showpiece. Here's the full pipeline:

**`app/services/ai_service.py`:**
```python
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

SYSTEM_PROMPT = """You are an expert equipment maintenance assistant for a manufacturing facility.
Answer questions based ONLY on the provided equipment manuals and maintenance documentation.
If the information is not in the provided context, say so clearly — do not make up answers.
Always cite the source document and page number when available."""

def get_rag_chain():
    embeddings = AzureOpenAIEmbeddings(
        azure_deployment="text-embedding-3-small",
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_KEY
    )
    vectorstore = Chroma(
        collection_name="equipment_manuals",
        embedding_function=embeddings,
        persist_directory="./chroma_db"
    )
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o",
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_KEY,
        temperature=0.1    # low temperature for factual maintenance questions
    )
    prompt = PromptTemplate.from_template(
        SYSTEM_PROMPT + "\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"
    )
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )

async def ask_question(question: str, equipment_context: str = "") -> dict:
    full_question = f"{equipment_context}\n\n{question}" if equipment_context else question
    chain = get_rag_chain()
    result = chain({"query": full_question})
    sources = [doc.metadata.get("source", "Unknown") for doc in result["source_documents"]]
    return {
        "answer": result["result"],
        "sources": list(set(sources))
    }

async def index_document(file_path: str, equipment_id: str = None):
    """Load a PDF, split into chunks, embed, store in ChromaDB."""
    from langchain_community.document_loaders import PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    loader = PyPDFLoader(file_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(pages)

    # Add metadata so we can filter by equipment later
    for chunk in chunks:
        chunk.metadata["equipment_id"] = equipment_id or "general"

    embeddings = AzureOpenAIEmbeddings(...)
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name="equipment_manuals",
        persist_directory="./chroma_db"
    )
```

**The diagnose endpoint goes further — it pulls real database context:**
```python
async def diagnose(equipment_id: str, symptom: str, db: AsyncSession) -> dict:
    equipment = await get_equipment_by_id(equipment_id, db)
    recent_logs = await get_recent_maintenance(equipment_id, db, limit=5)
    open_issues = await get_open_issues(equipment_id, db)

    context = f"""
    Equipment: {equipment.name} ({equipment.model_number})
    Type: {equipment.equipment_type}
    Status: {equipment.status}
    Location: {equipment.location}

    Recent maintenance (last 5 logs):
    {format_logs(recent_logs)}

    Current open issues:
    {format_issues(open_issues)}

    Reported symptom: {symptom}
    """

    return await ask_question(
        question=f"Based on the equipment history and symptom described, what is the likely cause and recommended action?",
        equipment_context=context
    )
```

---

## 12. Azure Deployment Plan

### Local → Production path:

**Step 1: Build and push Docker image**
```bash
# Login to Azure Container Registry
az acr login --name equiptrackregistry

# Build and tag
docker build -t equiptrackregistry.azurecr.io/equiptrack-api:v1.0 .

# Push
docker push equiptrackregistry.azurecr.io/equiptrack-api:v1.0
```

**Step 2: Provision Azure resources**
```bash
# Resource group
az group create --name equiptrack-rg --location eastus

# Azure Database for PostgreSQL Flexible Server
az postgres flexible-server create \
  --name equiptrack-db \
  --resource-group equiptrack-rg \
  --admin-user equiptrack \
  --admin-password <secure-password> \
  --sku-name Standard_B1ms

# Azure Container Apps environment
az containerapp env create \
  --name equiptrack-env \
  --resource-group equiptrack-rg \
  --location eastus

# Deploy the container
az containerapp create \
  --name equiptrack-api \
  --resource-group equiptrack-rg \
  --environment equiptrack-env \
  --image equiptrackregistry.azurecr.io/equiptrack-api:v1.0 \
  --target-port 8000 \
  --ingress external \
  --env-vars DATABASE_URL=secretref:db-url OPENAI_API_KEY=secretref:openai-key
```

**Step 3: Run Liquibase migrations against the production DB**
```bash
liquibase \
  --url="jdbc:postgresql://equiptrack-db.postgres.database.azure.com:5432/equiptrack_db" \
  --username=equiptrack \
  --password=<password> \
  --changeLogFile=migrations/changelog.xml \
  update
```

**Azure services used and why:**

| Service | Purpose | Why not X |
|---|---|---|
| Azure Container Apps | Run the FastAPI container | Simpler than AKS for a single service; handles HTTPS, scaling |
| Azure Database for PostgreSQL Flexible Server | Managed PostgreSQL | No server management; automated backups; same as dev |
| Azure Blob Storage | Store uploaded PDF manuals | Cheap, durable, accessible from any service |
| Azure AI Search | Vector store in production | Replaces ChromaDB; managed, scalable, integrates with Azure OpenAI |
| Azure Container Registry | Store Docker images | Private registry within Azure ecosystem |
| Azure Key Vault | Secrets (DB password, API keys) | Don't put secrets in environment variables directly in prod |

---

## 13. Alternative Approaches — What You Considered

This section makes you stand out in the interview. Knowing what you chose *and* what you rejected shows architectural maturity.

**Alembic vs Liquibase for migrations:**
Alembic is the Python-native migration tool — it autogenerates migrations by diff-ing your SQLModel models against the DB. Liquibase is language-agnostic (Java-based) and is what GM uses. Alembic would have been a more natural fit for a pure-Python project. Liquibase was chosen to match the team's tooling and to demonstrate the XML changeset format they actually use. For a Python-only team, Alembic would be the better default.

**SQLAlchemy vs SQLModel:**
SQLModel is a thin wrapper over SQLAlchemy that makes models dual-purpose (ORM + Pydantic validation). This reduces boilerplate and is ideal for FastAPI projects. The tradeoff: SQLModel is less mature and has fewer community resources than SQLAlchemy. For production-scale complexity (multiple schemas, stored procedures, complex joins), raw SQLAlchemy would give more control. For this project, SQLModel's simplicity was the right call.

**ChromaDB vs Pinecone vs Azure AI Search for the vector store:**
ChromaDB runs locally (no API key needed), perfect for development. Pinecone is a managed cloud vector database with a generous free tier. Azure AI Search is the production choice for Azure-deployed apps — it integrates natively with Azure OpenAI and supports hybrid search (vector + keyword). The decision: ChromaDB in development (zero cost, zero setup), Azure AI Search in production (native Azure integration). Never use Pinecone in production if everything else is on Azure — mixing cloud vendors complicates networking and security.

**Monolith vs microservices:**
This project is a monolith — one FastAPI app with multiple routers. It could be split into three services: `equipment-service`, `maintenance-service`, and `ai-service`. The reason not to: microservices add deployment complexity (separate containers, inter-service networking, distributed tracing) that isn't justified until the team is large enough that different parts of the codebase need to deploy independently. Start monolith, extract services when you hit a real scaling or team size problem.

**REST vs GraphQL:**
GraphQL would allow the frontend to request exactly the fields it needs (useful for the `/equipment/{id}/summary` endpoint where different dashboard views might need different subsets). REST was chosen for simplicity — it's what the GM stack uses, and a straightforward REST API is easier to document, test, and reason about for a junior team.

**Synchronous Flask vs async FastAPI:**
FastAPI with `async def` route handlers is the right choice for this app: the route handlers spend most of their time waiting for database I/O and LLM API responses, not doing CPU work. Async lets the server handle many simultaneous requests while waiting for I/O. Flask (synchronous) would block the event loop during every database query. The performance difference is especially dramatic for the AI endpoints which can take 2–5 seconds to respond.

---

## 14. Build Order — What to Build First

Don't try to build everything at once. Build in this exact order so you always have a working, runnable application at each step.

**Week 1 (MVP core):**
1. Project structure, `main.py`, `config.py`, `database.py`
2. Equipment model + Equipment router (CRUD only, no filters yet)
3. Connect to PostgreSQL via Docker Compose
4. Verify via Swagger UI at `/docs`
5. Write Liquibase changeset for equipment table, run it manually
6. Add Maintenance model + router (logs only)
7. Write first Pytest tests for equipment routes

**Week 2 (Polish + Quality):**
8. Issues model + router + status transition logic in service layer
9. Parts model + router + low-stock endpoint
10. Add query filters to GET /equipment (department, status, type)
11. Add GET /equipment/{id}/summary endpoint
12. Write Pytest tests for Issues (including transition validation)
13. Liquibase changesets for all remaining tables + indexes
14. Full Dockerfile + Docker Compose working end-to-end

**Week 3 (AI + Deploy):**
15. Documents upload endpoint (store in local filesystem for dev, Azure Blob in prod)
16. ChromaDB setup, `index_document` function
17. `/ai/ask` endpoint with LangChain RAG
18. `/ai/diagnose/{id}` endpoint with equipment context injection
19. Analytics endpoints (health score, dashboard)
20. Deploy to Azure Container Apps
21. README with architecture description, setup instructions, and screenshots

---

## 15. Resume Bullet Points

When you put this on your resume, frame it like this:

**Project: EquipTrack — Manufacturing Equipment Maintenance Platform**

- Built a production-grade REST API using **FastAPI (Python 3.12)** and **PostgreSQL**, with five normalized tables managing equipment, maintenance logs, issues, and spare parts inventory
- Implemented release-safe schema migrations using **Liquibase** with XML changesets covering table creation, column additions, and partial indexes
- Developed an AI-powered diagnostic endpoint using **LangChain** and **Azure OpenAI**, applying RAG (Retrieval-Augmented Generation) over equipment manuals stored in **ChromaDB**
- Achieved **90%+ test coverage** with **Pytest** and `TestClient`, covering route handlers, status transition validation, and database behavior with isolated test database sessions
- Containerized the full application stack (**FastAPI + PostgreSQL + ChromaDB**) using **Docker Compose** for local development and deployed to **Azure Container Apps** with **Azure Database for PostgreSQL**
- Designed clean separation between HTTP layer (routers) and business logic (services), with Pydantic schemas enforcing request validation and response serialization independently of ORM models

---

## 16. What to Say in the Interview

When they ask "tell me about a project you've worked on":

> "I built a manufacturing equipment maintenance system that mirrors exactly what your team is building — replacing Excel-based maintenance tracking with a structured API. The backend is FastAPI with PostgreSQL, I used SQLModel for the ORM, Liquibase for schema migrations, and Pytest for testing. I also added a LangChain RAG pipeline where maintenance crews can ask questions about their equipment manuals and get AI-generated diagnoses. The whole thing runs in Docker locally and I deployed it to Azure Container Apps. I can walk you through any part of it — the database schema, the migration strategy, how I structured the service layer, or how the RAG endpoint works."

Then stop talking. Let them ask the follow-up they're most interested in. You have a concrete, detailed answer for every direction they can take that question.

---

*Total estimated build time: 3–4 weeks at 2h weekdays + 3–4h weekends. Build the MVP (equipment + maintenance + docker + tests) in Week 1, and you already have a deployable project. The AI features and Azure deployment are the polish.*
