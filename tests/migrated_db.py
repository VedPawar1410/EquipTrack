"""A throwaway Postgres 16 + pgvector, migrated by the real Liquibase changelog.

Shared by the pytest suite (tests/conftest.py) and the RAG evaluation (evals/rag_eval.py), so both
always run against exactly the schema production gets.
"""
import contextlib
import os
import pathlib
from collections.abc import Iterator

# Colima keeps its Docker socket in the home directory; point the Docker SDK at it if present.
_colima_socket = pathlib.Path.home() / ".colima" / "default" / "docker.sock"
if "DOCKER_HOST" not in os.environ and _colima_socket.exists():
    os.environ["DOCKER_HOST"] = f"unix://{_colima_socket}"
    os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")

import docker  # noqa: E402
from testcontainers.community.postgres import PostgresContainer  # noqa: E402
from testcontainers.core.network import Network  # noqa: E402

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
LIQUIBASE_IMAGE = "liquibase/liquibase:4.29"


def _run_liquibase(network: Network, pg: PostgresContainer) -> None:
    container = docker.from_env().containers.run(
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


@contextlib.contextmanager
def migrated_postgres() -> Iterator[str]:
    """Yields an asyncpg connection URL; the containers are removed on exit."""
    with Network() as network:
        postgres = PostgresContainer(POSTGRES_IMAGE, driver="asyncpg").with_network(network).with_network_aliases("db")
        with postgres as pg:
            _run_liquibase(network, pg)
            yield pg.get_connection_url()
