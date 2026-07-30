from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


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
    id: UUID
    equipment_id: UUID
    created_at: datetime
    updated_at: datetime | None = None

