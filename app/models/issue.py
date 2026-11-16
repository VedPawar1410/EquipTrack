from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship

from app.models.equipment import EquipmentTable
from app.schemas.common import utc_now
from app.schemas.issue import STATUS, SharedIssue


class IssueTable(SharedIssue, table=True):
    __tablename__ = "issues"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    equipment_id: UUID = Field(foreign_key="equipment.id")
    status: STATUS = Field(
        default=STATUS.OPEN,
        sa_type=SAEnum(STATUS, native_enum=False, create_type=False, values_callable=lambda enum_cls: [e.value for e in enum_cls])  # type: ignore
    )
    # Display names (kept for history) + real user references added in v1.3.
    reported_by: str = Field(max_length=100)
    reported_by_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    assigned_to: Optional[str] = Field(default=None, max_length=100)
    assigned_to_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: Optional[datetime] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None)

    # Connects back to the parent table for ORM usage
    equipment: Optional[EquipmentTable] = Relationship(back_populates="issues")
