from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


class SharedPart(SQLModel):
    part_name: str = Field(max_length=100)
    part_number: str | None = Field(default=None, max_length=100)
    quantity_in_stock: int = Field(default=0, ge=0)   # matches CHECK (quantity_in_stock >= 0): zero stock is valid
    reorder_threshold: int = Field(default=2, ge=0)   # matches CHECK (reorder_threshold >= 0)
    unit_cost_usd: float | None = None
    supplier: str | None = Field(default=None, max_length=100)

class PartIn(SharedPart):
    pass

class PartOut(SharedPart):
    id: UUID
    equipment_id: UUID
    created_at: datetime
    updated_at: datetime | None = None

