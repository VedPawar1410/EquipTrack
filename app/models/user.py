from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.schemas.common import utc_now
from app.schemas.user import SharedUser


class UserTable(SharedUser, table=True):
    __tablename__ = "users"  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    hashed_password: str = Field(max_length=255)
    is_active: bool = True  # deactivate, never delete: their name stays on historical records
    created_at: datetime = Field(default_factory=utc_now)
