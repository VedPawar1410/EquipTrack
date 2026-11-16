from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlmodel import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.schemas.common import UTCDatetime

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

class SharedMaintenance(SQLModel):
    log_type: LogType = Field(
        sa_type=SAEnum(LogType, native_enum=False, create_type=False,
        values_callable=lambda enum_cls: [e.value for e in enum_cls]) # type: ignore
    )
    performed_at: UTCDatetime  # TIMESTAMPTZ column; date-only input becomes UTC midnight
    description: str
    duration_minutes: int | None = Field(default=None, gt=0)
    cost_usd: float | None = None
    next_scheduled_at: UTCDatetime | None = None

class MaintenanceIn(SharedMaintenance):
    # Who did the work. Defaults to the logged-in user; can be a name (e.g. an outside contractor).
    performed_by: str | None = Field(default=None, max_length=100)

class MaintenanceOut(SharedMaintenance):
    id: UUID
    equipment_id: UUID
    performed_by: str
    performed_by_id: UUID | None = None  # the account that logged it
    created_at: datetime  # read from the row; it used to be generated at response time



