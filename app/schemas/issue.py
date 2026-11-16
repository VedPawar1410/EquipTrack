from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlmodel import Enum as SAEnum
from sqlmodel import Field, SQLModel


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class STATUS(str, Enum):
    OPEN = "Open"
    RESOLVED = "Resolved"
    CLOSED = "Closed"
    INPROGRESS = "In Progress"

class SharedIssue(SQLModel):
    title: str = Field(max_length=200)
    description: str | None = None
    severity: Severity = Field(
        sa_type=SAEnum(Severity, native_enum=False, create_type=False,
        values_callable=lambda enum_cls: [e.value for e in enum_cls]) # type: ignore
    )
    error_code: str | None = Field(default=None, max_length=50)

class IssueIn(SharedIssue):
    equipment_id: UUID
    # reporter = the logged-in user (set server-side); assignment happens after creation.

class IssueOut(SharedIssue):
    id: UUID
    equipment_id: UUID
    status: STATUS
    reported_by: str
    reported_by_id: Optional[UUID] = None
    assigned_to: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

class IssueStatusUpdate(SQLModel):
    status: STATUS


class IssueAssign(SQLModel):
    assigned_to: str = Field(min_length=1, max_length=50, description="Username of an active user")
