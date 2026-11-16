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
    reported_by: str = Field(max_length=100)
    error_code: str | None = Field(default=None, max_length=50)

class IssueIn(SharedIssue):
    equipment_id: UUID
    # you cant assign the issue to a person while creating an issue, you cna only do it after the issue is created, is that right or not, will have to check.

class IssueOut(SharedIssue):
    id: UUID
    equipment_id: UUID  
    status: STATUS
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

