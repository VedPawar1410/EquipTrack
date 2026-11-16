"""Guards that the Liquibase-built schema and the SQLModel models stay aligned."""
import pathlib
import re

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects import postgresql
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers every table)

PG = postgresql.dialect()
MIGRATIONS = pathlib.Path(__file__).resolve().parent.parent / "migrations"


def _family(sql_type: str) -> str:
    s = sql_type.upper()
    for key, fam in [("UUID", "uuid"), ("TIMESTAMP", "timestamp"), ("DATETIME", "timestamp"), ("DATE", "date"),
                     ("BOOL", "bool"), ("INT", "int"), ("NUMERIC", "number"), ("FLOAT", "number"),
                     ("DOUBLE", "number"), ("CHAR", "string"), ("TEXT", "string")]:
        if key in s:
            return fam
    return s


async def test_models_match_migrated_schema(engine):
    async with engine.connect() as conn:
        db = await conn.run_sync(lambda c: {t: {col["name"]: col for col in inspect(c).get_columns(t)}
                                            for t in SQLModel.metadata.tables})
    problems = []
    for name, table in SQLModel.metadata.tables.items():
        for column in table.columns:
            live = db[name].get(column.name)
            if live is None:
                problems.append(f"{name}.{column.name} is in the model but not the database")
                continue
            if _family(column.type.compile(dialect=PG)) != _family(str(live["type"])):
                problems.append(f"{name}.{column.name}: model {column.type} vs database {live['type']}")
            if not column.primary_key and column.nullable and not live["nullable"] and not live.get("default"):
                problems.append(f"{name}.{column.name}: model allows NULL but the database forbids it")
        for extra in set(db[name]) - {c.name for c in table.columns}:
            problems.append(f"{name}.{extra} is in the database but not the model")
    assert problems == []


async def test_every_changeset_was_applied(engine):
    declared = sum(len(re.findall(r"<changeSet\b", p.read_text())) for p in MIGRATIONS.rglob("*.xml"))
    async with engine.connect() as conn:
        applied = (await conn.execute(text("SELECT count(*) FROM databasechangelog"))).scalar_one()
    assert applied == declared


@pytest.mark.parametrize("sql", [
    # The API validates these too, but the database must reject bad data from any other writer.
    "INSERT INTO parts (equipment_id, part_name, quantity_in_stock) VALUES (:eid, 'p', -1)",
    "INSERT INTO maintenance_logs (equipment_id, log_type, performed_by, performed_at, description, duration_minutes)"
    " VALUES (:eid, 'Inspection', 'x', now(), 'd', 0)",
    "INSERT INTO users (username, email, hashed_password, role) VALUES ('x', 'x@x.io', 'h', 'boss')",
    "INSERT INTO equipment (name, serial_number, equipment_type, location, department)"
    " SELECT name, serial_number, equipment_type, location, department FROM equipment WHERE id = :eid",
])
async def test_database_rejects_invalid_rows(engine, equipment, sql):
    async with engine.connect() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(text(sql), {"eid": equipment["id"]})


async def test_low_stock_query_uses_partial_index(engine):
    async with engine.connect() as conn:
        await conn.execute(text("SET enable_seqscan = off"))
        plan = "\n".join(r[0] for r in await conn.execute(
            text("EXPLAIN SELECT * FROM parts WHERE quantity_in_stock <= reorder_threshold")))
    assert "idx_parts_low_stock" in plan
