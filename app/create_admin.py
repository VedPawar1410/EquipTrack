"""Create the first admin account (there is no public sign-up, so someone has to be first).

    docker compose exec app python -m app.create_admin --username admin --email admin@example.com

The password is read from ADMIN_PASSWORD if set, otherwise prompted for (never a CLI argument,
which would end up in shell history).
"""
import argparse
import asyncio
import getpass
import os
import sys

from sqlmodel import or_, select

from app.core.database import async_session_maker, engine
from app.models.user import UserTable
from app.schemas.user import Role, UserCreate
from app.services.auth_service import hash_password


async def main(username: str, email: str, password: str) -> int:
    data = UserCreate(username=username, email=email, password=password, role=Role.ADMIN)  # validates
    async with async_session_maker() as db:
        exists = (await db.execute(select(UserTable).where(
            or_(UserTable.username == data.username, UserTable.email == data.email)))).first()
        if exists:
            print(f"A user with username '{data.username}' or email '{data.email}' already exists.", file=sys.stderr)
            return 1
        db.add(UserTable(username=data.username, email=data.email, role=Role.ADMIN,
                         hashed_password=hash_password(data.password)))
        await db.commit()
    await engine.dispose()
    print(f"Admin '{data.username}' created.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    pw = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password (min 8 chars): ")
    sys.exit(asyncio.run(main(args.username, args.email, pw)))
