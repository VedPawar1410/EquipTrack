from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import or_, select

from app.core.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import UserTable
from app.schemas.user import PasswordChange, Role, RoleUpdate, Token, UserCreate, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
admin_only = require_role(Role.ADMIN)


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """OAuth2 password flow (form fields `username`, `password`). Username or email both work."""
    statement = select(UserTable).where(or_(UserTable.username == form.username, UserTable.email == form.username))
    user = (await db.execute(statement)).scalar_one_or_none()
    if not auth_service.authenticate(user, form.password):
        # One message for every failure: don't reveal whether the username exists.
        raise HTTPException(status_code=401, detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return Token(access_token=auth_service.create_access_token(user.id))  # type: ignore[union-attr]


@router.get("/me", response_model=UserOut)
async def read_me(user: UserTable = Depends(get_current_user)):
    return user


@router.post("/me/password", status_code=204)
async def change_my_password(
    body: PasswordChange,
    user: UserTable = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not auth_service.verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = auth_service.hash_password(body.new_password)
    await db.commit()
    return Response(status_code=204)


@router.post("/users", response_model=UserOut, status_code=201, dependencies=[Depends(admin_only)])
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    user = UserTable(
        username=body.username, email=body.email, role=body.role,
        hashed_password=auth_service.hash_password(body.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already exists") from None
    await db.refresh(user)
    return user


@router.get("/users", response_model=List[UserOut], dependencies=[Depends(admin_only)])
async def list_users(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(UserTable).order_by(UserTable.username))).scalars().all()


async def _get_user_or_404(user_id: UUID, db: AsyncSession) -> UserTable:
    user = await db.get(UserTable, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def change_role(
    user_id: UUID, body: RoleUpdate,
    admin: UserTable = Depends(admin_only), db: AsyncSession = Depends(get_db),
):
    user = await _get_user_or_404(user_id, db)
    if user.id == admin.id:
        # Guard against an admin locking everyone out by demoting the last admin account.
        raise HTTPException(status_code=422, detail="You cannot change your own role")
    user.role = body.role
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(user_id: UUID, admin: UserTable = Depends(admin_only), db: AsyncSession = Depends(get_db)):
    user = await _get_user_or_404(user_id, db)
    if user.id == admin.id:
        raise HTTPException(status_code=422, detail="You cannot deactivate yourself")
    user.is_active = False  # their existing tokens stop working on the next request
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/activate", response_model=UserOut, dependencies=[Depends(admin_only)])
async def activate_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await _get_user_or_404(user_id, db)
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user
