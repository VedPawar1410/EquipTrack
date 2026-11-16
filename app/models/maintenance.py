from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship

from app.models.equipment import EquipmentTable
from app.schemas.common import utc_now
from app.schemas.maintenance import SharedMaintenance


class MaintenanceTable(SharedMaintenance, table=True):
    __tablename__ = "maintenance_logs"  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    equipment_id: UUID = Field(foreign_key="equipment.id")
    performed_by: str = Field(max_length=100)
    performed_by_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=utc_now)

    # Connects back to the parent table for ORM usage
    equipment: Optional[EquipmentTable] = Relationship(back_populates="maintenance_logs")
