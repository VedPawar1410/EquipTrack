import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import field_validator
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class Role(str, Enum):
    TECHNICIAN = "technician"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class SharedUser(SQLModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(max_length=100)
    role: Role = Field(
        default=Role.TECHNICIAN,
        sa_type=SAEnum(Role, native_enum=False, create_type=False,
                       values_callable=lambda enum_cls: [e.value for e in enum_cls]),  # type: ignore
    )


class UserCreate(SharedUser):
    """Admins create accounts; there is no public sign-up (plant accounts are provisioned, like badges)."""
    password: str = Field(min_length=8, max_length=128)

    # Explicit validators: SQLModel's Field(regex=...) is not enforced under Pydantic v2
    # (a test caught "has spaces" being accepted as a username).
    @field_validator("username")
    @classmethod
    def username_chars(cls, value: str) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", value):
            raise ValueError("username may only contain letters, digits, '.', '_' and '-'")
        return value

    @field_validator("email")
    @classmethod
    def email_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("not a valid email address")
        return value.lower()


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
