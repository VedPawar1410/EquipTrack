from sqlmodel import Relationship, SQLModel
from datetime import date
from pydantic import Field
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field
from enum import Enum
from sqlmodel import Enum as SAEnum
from datetime import date, datetime

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

class IssueTable(SharedIssue, table=True):
    __tablename__ = "issues" # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    equipment_id: UUID = Field(foreign_key="equipment.id")  # Assuming your equipment table is named 'equipment'
    status: STATUS = Field(
        default=STATUS.OPEN,
        sa_type=SAEnum(STATUS, native_enum=False, create_type=False, values_callable=lambda enum_cls: [e.value for e in enum_cls]) #type: ignore
    )
    assigned_to: Optional[str] = None
    created_at: date = Field(default_factory=date.today)
    resolved_at: Optional[date] = Field(default=None)

    # Connects back to the parent table for ORM usage
    equipment: Optional[EquipmentTable] = Relationship(back_populates="issues")