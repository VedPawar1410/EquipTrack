from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship

from app.models.equipment import EquipmentTable
from app.schemas.common import utc_now
from app.schemas.maintenance import SharedMaintainance


class MaintainanceTable(SharedMaintainance, table=True):
    __tablename__ = "maintenance_logs"  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # CRITICAL: Define the foreign key connection here
    # Use format: "lowercase_table_name.column_name"
    equipment_id: UUID = Field(foreign_key="equipment.id")
    created_at: datetime = Field(default_factory=utc_now)

    # Connects back to the parent table for ORM usage
    equipment: Optional[EquipmentTable] = Relationship(back_populates="maintenance_logs")
