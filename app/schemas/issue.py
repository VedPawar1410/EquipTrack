from datetime import date
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
    title: str  
    description: str | None = None
    severity: Severity = Field(
        sa_type=SAEnum(Severity, native_enum=False, create_type=False,
        values_callable=lambda enum_cls: [e.value for e in enum_cls]) # type: ignore
    )
    reported_by: str
    error_code: str | None = None

class IssueIn(SharedIssue):
    equipment_id: UUID
    # you cant assign the issue to a person while creating an issue, you cna only do it after the issue is created, is that right or not, will have to check.

class IssueOut(SharedIssue):
    id: UUID
    equipment_id: UUID  
    assigned_to: Optional[str] = None
    created_at: date
    resolved_at: Optional[date] = None

