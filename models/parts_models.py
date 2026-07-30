from uuid import UUID, uuid4
from sqlmodel import Field
from sqlmodel import Relationship
from typing import Optional
from .equipment_models import EquipmentTable
from datetime import datetime, date
from sqlmodel import SQLModel


class SharedPart(SQLModel):
    part_name: str
    part_number: str | None = None
    quantity_in_stock: int = Field(default=0, gt=0)
    reorder_threshold: int = Field(default=2, gt=0)
    unit_cost_usd: float | None = None
    supplier: str | None = None

class PartIn(SharedPart):
    pass

class PartOut(SharedPart):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    equipment_id: UUID = Field(foreign_key="equipment.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=datetime.now)

class PartTable(SharedPart, table=True):
    __tablename__ = "parts" # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    equipment_id: UUID = Field(foreign_key="equipment.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Connects back to the parent table for ORM usage
    equipment: Optional[EquipmentTable] = Relationship(back_populates="parts")  