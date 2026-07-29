from sqlmodel import SQLModel
from datetime import date, datetime
from uuid import UUID, uuid4
from pydantic import Field
from sqlmodel import Field
from sqlmodel import Relationship
from typing import Optional
from .equipment_models import EquipmentTable
from enum import Enum
from sqlmodel import Enum as SAEnum

class LogType(str, Enum):
    # Planned / preventive
    SCHEDULED = "Scheduled"
    CALIBRATION = "Calibration"
    CLEANING = "Cleaning"
    INSTALLATION = "Installation"
    SOFTWARE_UPDATE = "Software Update"
    SAFETY_AUDIT = "Safety Audit"
 
    # Reactive / unplanned
    EMERGENCY = "Emergency"
    CORRECTIVE = "Corrective"
    WARRANTY_REPAIR = "Warranty Repair"
 
    # Condition-based
    PREDICTIVE = "Predictive"
 
    # Routine check
    INSPECTION = "Inspection"
 
    # Major / lifecycle events
    OVERHAUL = "Overhaul"
    RETROFIT = "Retrofit"
    DECOMMISSIONING = "Decommissioning"

class SharedMaintainance(SQLModel):
    log_type: LogType = Field(
        sa_type=SAEnum(LogType, native_enum=False, create_type=False,
        values_callable=lambda enum_cls: [e.value for e in enum_cls]) # type: ignore
    )
    performed_by: str
    performed_at: date
    description: str
    duration_minutes: int | None = Field(default=None, gt=0)
    cost_usd: float | None = None
    next_scheduled_at: date | None = None

class MaintainanceIn(SharedMaintainance):
    pass

class MaintainanceOut(SharedMaintainance):
    id: UUID
    created_at: datetime = Field(default_factory=datetime.now)

class MaintainanceTable(SharedMaintainance, table=True):
    __tablename__ = "maintenance_logs" # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # CRITICAL: Define the foreign key connection here
    # Use format: "lowercase_table_name.column_name"
    equipment_id: UUID = Field(foreign_key="equipment.id")
    
    # Connects back to the parent table for ORM usage
    equipment: Optional[EquipmentTable] = Relationship(back_populates="maintenance_logs")

