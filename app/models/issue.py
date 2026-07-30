from datetime import date
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship

from app.models.equipment import EquipmentTable
from app.schemas.issue import STATUS, SharedIssue


class IssueTable(SharedIssue, table=True):
    __tablename__ = "issues"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    equipment_id: UUID = Field(foreign_key="equipment.id")  # Assuming your equipment table is named 'equipment'
    status: STATUS = Field(
        default=STATUS.OPEN,
        sa_type=SAEnum(STATUS, native_enum=False, create_type=False, values_callable=lambda enum_cls: [e.value for e in enum_cls])  # type: ignore
    )
    assigned_to: Optional[str] = None
    created_at: date = Field(default_factory=date.today)
    resolved_at: Optional[date] = Field(default=None)

    # Connects back to the parent table for ORM usage
    equipment: Optional[EquipmentTable] = Relationship(back_populates="issues")
