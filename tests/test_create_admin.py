from sqlmodel import select

from app import create_admin
from app.core import database
from app.models.user import UserTable


async def test_create_admin_command(session_maker, monkeypatch, capsys):
    monkeypatch.setattr(create_admin, "async_session_maker", session_maker)
    monkeypatch.setattr(create_admin, "engine", database.engine)  # dispose() on the unused default engine is harmless

    assert await create_admin.main("plantadmin", "plant.admin@plant.test", "Admin-Pass-1") == 0
    async with session_maker() as session:
        user = (await session.execute(select(UserTable).where(UserTable.username == "plantadmin"))).scalar_one()
    assert user.role == "admin" and user.hashed_password != "Admin-Pass-1"

    assert await create_admin.main("plantadmin", "other@plant.test", "Admin-Pass-1") == 1   # duplicate refused
    assert "already exists" in capsys.readouterr().err
