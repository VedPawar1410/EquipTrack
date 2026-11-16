from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.equipment import EquipmentTable
from app.models.user import UserTable
from app.schemas.user import Role
from app.services import auth_service

# tokenUrl powers the "Authorize" button in /docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserTable:
    """401 unless the request carries a valid token for an active user."""
    unauthorized = HTTPException(
        status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        user_id = auth_service.decode_access_token(token)
    except auth_service.InvalidToken:
        raise unauthorized from None  # don't chain the JWT library's error into the response path
    user = await db.get(UserTable, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_role(minimum: Role):
    """Dependency factory: 403 unless the current user's role is at least `minimum`."""

    async def checker(user: UserTable = Depends(get_current_user)) -> UserTable:
        if not auth_service.has_role(user.role, minimum):
            raise HTTPException(status_code=403, detail="Not authorized for this action")
        return user

    return checker


async def get_equipment_or_404(
    equipment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EquipmentTable:
    """Shared existence check for any route nested under /equipment/{equipment_id}/..."""
    equipment = await db.get(EquipmentTable, equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return equipment
