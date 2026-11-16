from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class Role(str, Enum):
    TECHNICIAN = "technician"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class SharedUser(SQLModel):
    username: str = Field(min_length=3, max_length=50, regex=r"^[a-zA-Z0-9._-]+$")
    email: str = Field(max_length=100, regex=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: Role = Field(
        default=Role.TECHNICIAN,
        sa_type=SAEnum(Role, native_enum=False, create_type=False,
                       values_callable=lambda enum_cls: [e.value for e in enum_cls]),  # type: ignore
    )


class UserCreate(SharedUser):
    """Admins create accounts; there is no public sign-up (plant accounts are provisioned, like badges)."""
    password: str = Field(min_length=8, max_length=128)


class UserOut(SharedUser):
    # hashed_password is deliberately absent: it can never leak through a response.
    id: UUID
    is_active: bool
    created_at: datetime


class RoleUpdate(SQLModel):
    role: Role


class PasswordChange(SQLModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
