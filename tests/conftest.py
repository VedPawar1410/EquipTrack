"""Shared test fixtures.

How the test database works:
1. Start a throwaway Postgres 16 container (testcontainers) on a private Docker network.
2. Run the REAL Liquibase changelog against it in a Liquibase container, exactly like
   docker-compose does. Tests therefore exercise the migrated schema, not SQLModel's
   create_all(), so a broken migration or model/schema drift fails the suite.
3. Every request in a test gets its own session from a pool on that database, like production.
4. After each test, all app tables are truncated, so tests never depend on each other.

Requires Docker (Docker Desktop, Colima or the GitHub Actions runner).
"""
import os
import pathlib

# Settings are read at import time, so set test values before importing the app.
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-for-the-pytest-suite-0123")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost:1/unused")  # replaced via get_db override

# Colima keeps its Docker socket in the home directory; point the Docker SDK at it if present.
_colima_socket = pathlib.Path.home() / ".colima" / "default" / "docker.sock"
if "DOCKER_HOST" not in os.environ and _colima_socket.exists():
    os.environ["DOCKER_HOST"] = f"unix://{_colima_socket}"
    os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")

import docker  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from testcontainers.community.postgres import PostgresContainer  # noqa: E402
from testcontainers.core.network import Network  # noqa: E402

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import UserTable  # noqa: E402
from app.schemas.user import Role  # noqa: E402
from app.services.auth_service import create_access_token, hash_password  # noqa: E402

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"
LIQUIBASE_IMAGE = "liquibase/liquibase:4.29"
PASSWORD = "Correct-Horse-9"


def _run_liquibase(network: Network, pg: PostgresContainer) -> None:
    client = docker.from_env()
    container = client.containers.run(
        LIQUIBASE_IMAGE,
        command=[
            "--search-path=/liquibase/changelog", "--changelog-file=changelog.xml",
            "--url=jdbc:postgresql://db:5432/" + pg.dbname,
            f"--username={pg.username}", f"--password={pg.password}", "update",
        ],
        volumes={str(MIGRATIONS_DIR): {"bind": "/liquibase/changelog", "mode": "ro"}},
        network=network.name,
        detach=True,
    )
    try:
        status = container.wait(timeout=180)["StatusCode"]
        if status != 0:
            raise RuntimeError("Liquibase update failed:\n" + container.logs().decode()[-4000:])
    finally:
        container.remove(force=True)


@pytest.fixture(scope="session")
def database_url():
    with Network() as network:
        postgres = PostgresContainer("postgres:16", driver="asyncpg").with_network(network).with_network_aliases("db")
        with postgres as pg:
            _run_liquibase(network, pg)
            yield pg.get_connection_url()


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
    yield
    app.dependency_overrides.clear()


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
