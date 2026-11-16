"""Shared test fixtures.

How the test database works:
1. Start a throwaway Postgres 16 + pgvector container (testcontainers) on a private Docker network.
2. Run the REAL Liquibase changelog against it in a Liquibase container, exactly like
   docker-compose does. Tests therefore exercise the migrated schema, not SQLModel's
   create_all(), so a broken migration or model/schema drift fails the suite.
3. Every request in a test gets its own session from a pool on that database, like production.
4. After each test, all app tables are truncated, so tests never depend on each other.

Requires Docker (Docker Desktop, Colima or the GitHub Actions runner).
"""
import os

# Settings are read at import time, so set test values before importing the app.
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-for-the-pytest-suite-0123")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost:1/unused")  # replaced via get_db override
os.environ.setdefault("EMBEDDING_PROVIDER", "hashing")  # deterministic fake: no model download in CI
# Force-blank the LLM keys (env vars beat a developer's .env): the suite must never call a real LLM.
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.database import get_db, get_session_maker  # noqa: E402
from app.dependencies import ai_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import UserTable  # noqa: E402
from app.schemas.user import Role  # noqa: E402
from app.services.auth_service import create_access_token, hash_password  # noqa: E402
from app.services.llm import get_chat_model  # noqa: E402
from tests.migrated_db import migrated_postgres  # noqa: E402

PASSWORD = "Correct-Horse-9"


@pytest.fixture(scope="session")
def database_url():
    with migrated_postgres() as url:
        yield url


@pytest.fixture(scope="session")
async def engine(database_url):
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def session_maker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _use_test_database(session_maker):
    async def override_get_db():
        async with session_maker() as session:  # a fresh session per request, like production
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_maker] = lambda: session_maker  # background indexing uses the test DB too
    app.dependency_overrides[get_chat_model] = lambda: None  # no LLM unless a test injects a fake
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _fresh_ai_limits():
    ai_limiter.reset()  # the limiter is process-wide; no test may inherit another's request count


@pytest.fixture(autouse=True)
async def _clean_tables(engine):
    yield
    async with engine.begin() as conn:
        # CASCADE also empties every table that references these (logs, issues, parts, documents).
        await conn.execute(text("TRUNCATE equipment, users, documents CASCADE"))


@pytest.fixture(scope="session")
def password_hash():
    return hash_password(PASSWORD)  # Argon2 is deliberately slow: hash once per run


@pytest.fixture
async def users(session_maker, password_hash) -> dict[str, UserTable]:
    """One active user per role, plus an inactive technician."""
    rows = {
        "admin": UserTable(username="admin", email="admin@plant.test", role=Role.ADMIN, hashed_password=password_hash),
        "supervisor": UserTable(username="sup", email="sup@plant.test", role=Role.SUPERVISOR, hashed_password=password_hash),
        "technician": UserTable(username="tech", email="tech@plant.test", role=Role.TECHNICIAN, hashed_password=password_hash),
        "inactive": UserTable(username="gone", email="gone@plant.test", role=Role.TECHNICIAN,
                              hashed_password=password_hash, is_active=False),
    }
    async with session_maker() as session:
        session.add_all(rows.values())
        await session.commit()
    return rows


def _client(token: str | None = None) -> AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1", headers=headers)


@pytest.fixture
async def anon():
    async with _client() as c:
        yield c


@pytest.fixture
async def admin(users):
    async with _client(create_access_token(users["admin"].id)) as c:
        yield c


@pytest.fixture
async def supervisor(users):
    async with _client(create_access_token(users["supervisor"].id)) as c:
        yield c


@pytest.fixture
async def technician(users):
    async with _client(create_access_token(users["technician"].id)) as c:
        yield c


@pytest.fixture
def clients(admin, supervisor, technician) -> dict[str, AsyncClient]:
    """For parametrised role-matrix tests: clients["supervisor"], ..."""
    return {"admin": admin, "supervisor": supervisor, "technician": technician}


# ---------- small data builders (go through the API, so they also exercise it)

EQUIPMENT = {
    "name": "CNC Lathe A3", "model_number": "HAAS-ST-30", "serial_number": "SN-0001",
    "equipment_type": "CNC Machine", "location": "Floor A, Bay 3", "department": "Machining",
    "purchased_at": "2022-03-15", "warranty_expires_at": "2027-03-15",
}


@pytest.fixture
def make_equipment(admin):
    counter = {"n": 0}

    async def _make(**overrides) -> dict:
        counter["n"] += 1
        body = {**EQUIPMENT, "serial_number": f"SN-{counter['n']:04d}", **overrides}
        response = await admin.post("/equipment", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
async def equipment(make_equipment) -> dict:
    return await make_equipment()


def make_pdf(pages: list[str]) -> bytes:
    """A minimal, valid text PDF (one Helvetica line per entry in `pages`), built by hand so the
    tests need no PDF-writing library."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    font_id = 3 + 2 * len(pages)
    for i, page_text in enumerate(pages):
        safe = page_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET"
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
                       f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out
