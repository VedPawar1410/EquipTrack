"""The demo seed: creates a full plant once, is safe to re-run, and never touches existing passwords."""
from sqlalchemy import func, select

from app import seed_demo
from app.core import database
from app.models.document import DocumentTable
from app.models.equipment import EquipmentTable
from app.models.issue import IssueTable
from app.models.part import PartTable
from app.models.user import UserTable
from app.services.auth_service import verify_password


async def count(session_maker, model):
    async with session_maker() as db:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_creates_a_plant_and_is_idempotent(session_maker, monkeypatch, capsys):
    monkeypatch.setattr(seed_demo, "async_session_maker", session_maker)
    monkeypatch.setattr(seed_demo, "engine", database.engine)  # dispose() on the unused default engine is harmless

    await seed_demo.seed()
    totals = {m.__name__: await count(session_maker, m) for m in (UserTable, EquipmentTable, IssueTable, PartTable)}
    assert totals == {"UserTable": len(seed_demo.DEMO_USERS), "EquipmentTable": len(seed_demo.MACHINES),
                      "IssueTable": len(seed_demo.ISSUES), "PartTable": len(seed_demo.PARTS)}
    async with session_maker() as db:
        documents = (await db.execute(select(DocumentTable))).scalars().all()
    assert len(documents) == 4 and all(d.is_indexed for d in documents)
    assert sum(d.equipment_id is None for d in documents) == 1          # the plant-wide lockout procedure

    await seed_demo.seed()                                              # second run adds nothing
    assert await count(session_maker, EquipmentTable) == len(seed_demo.MACHINES)
    assert await count(session_maker, DocumentTable) == 4
    assert "Seeded: 0 machines, 0 manuals" in capsys.readouterr().out


async def test_seed_never_changes_an_existing_users_password(session_maker, monkeypatch, password_hash):
    monkeypatch.setattr(seed_demo, "async_session_maker", session_maker)
    monkeypatch.setattr(seed_demo, "engine", database.engine)
    async with session_maker() as db:
        db.add(UserTable(username="priya", email="priya@plant.test", role="admin", hashed_password=password_hash))
        await db.commit()

    await seed_demo.seed()
    async with session_maker() as db:
        priya = (await db.execute(select(UserTable).where(UserTable.username == "priya"))).scalar_one()
    assert priya.hashed_password == password_hash


async def test_admin_gets_the_private_password_when_one_is_set(session_maker, monkeypatch):
    """On a public deployment the admin password must not be the published one."""
    monkeypatch.setattr(seed_demo, "async_session_maker", session_maker)
    monkeypatch.setattr(seed_demo, "engine", database.engine)
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "Private-Admin-Pass-42")

    await seed_demo.seed()
    async with session_maker() as db:
        users = {u.username: u for u in (await db.execute(select(UserTable))).scalars()}
    published = {name: password for name, _, _, password in seed_demo.DEMO_USERS}
    assert verify_password("Private-Admin-Pass-42", users["priya"].hashed_password)
    assert not verify_password(published["priya"], users["priya"].hashed_password)
    assert verify_password(published["ravi"], users["ravi"].hashed_password)   # other demo logins unchanged
