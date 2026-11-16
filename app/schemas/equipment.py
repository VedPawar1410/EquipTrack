from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


#enums - research real world types and put here
class EquipmentType(str, Enum):
    # Stamping
    STAMPING_PRESS = "Stamping Press"
    COIL_LINE = "Coil Line"

    # Body Shop / Welding
    WELDING_ROBOT = "Welding Robot"
    SPOT_WELDER = "Spot Welder"
    ROBOTIC_ARM = "Robotic Arm"

    # Paint Shop
    PAINT_ROBOT = "Paint Robot"
    PAINT_BOOTH = "Paint Booth"
    ECOAT_SYSTEM = "E-Coat System"
    CURING_OVEN = "Curing Oven"

    # Powertrain / Machining
    CNC_MACHINE = "CNC Machine"
    HONING_MACHINE = "Honing Machine"
    GRINDER = "Grinder"
    DRILL_PRESS = "Drill Press"
    LASER_CUTTER = "Laser Cutter"
    PLASMA_CUTTER = "Plasma Cutter"
    WATERJET_CUTTER = "Waterjet Cutter"

    # General Assembly
    CONVEYOR = "Conveyor"
    ASSEMBLY_ROBOT = "Assembly Robot"
    TORQUE_TOOL_STATION = "Torque Tool Station"
    AGV = "Automated Guided Vehicle"

    # Quality / Metrology
    MEASURING = "Measuring Equipment"
    VISION_SYSTEM = "Vision System"
    TEST_STAND = "Test Stand"
    DYNAMOMETER = "Dynamometer"

    # Material Handling
    FORKLIFT = "Forklift"
    OVERHEAD_CRANE = "Overhead Crane"
    HYDRAULIC_LIFT = "Hydraulic Lift"
    PALLETIZER = "Palletizer"

    # Facilities / Utilities
    AIR_COMPRESSOR = "Air Compressor"
    BOILER = "Boiler"
    HVAC_UNIT = "HVAC Unit"
    GENERATOR = "Generator"
    WATER_TREATMENT_SYSTEM = "Water Treatment System"


class STATUS(str, Enum):
    ACTIVE = "active"
    UNDER_MAINTENANCE = "under maintenance"
    RETIRED = "retired"

class SharedEquipment(SQLModel):
    # max_length mirrors the VARCHAR sizes in the migrations: too-long input is a 422, not a DB error
    name: str = Field(max_length=100)
    model_number: str | None = Field(default=None, max_length=50)
    serial_number: str = Field(max_length=100)
    # This keeps validation in Python, but saves as standard VARCHAR in Postgres
    # https://share.google/aimode/5s3vd8NgXmbcTjTVj
    equipment_type: EquipmentType = Field(
        sa_type=SAEnum(EquipmentType, native_enum=False, create_type=False,
        values_callable=lambda enum_cls: [e.value for e in enum_cls]) # type: ignore
    )
    location: str = Field(max_length=100)
    department: str = Field(max_length=100)
    purchased_at: date | None = None         # unknown for older machines
    warranty_expires_at: date | None = None


class EquipmentIn(SharedEquipment):
    # Example shown in /docs. Lives on the request schema (not the shared base) so the
    # table model's own SQLModel config is left alone.
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Robotic Arm Alpha",
            "model_number": "RA-2000-X",
            "serial_number": "SN-987654321",
            "equipment_type": "Robotic Arm",  # an EquipmentType value
            "location": "Bay 4, Assembly Line A",
            "department": "Body Shop",
            "purchased_at": "2026-01-15",
            "warranty_expires_at": "2031-01-15",
        }
    })


class EquipmentOut(SharedEquipment):
    id: UUID
    status: STATUS = STATUS.ACTIVE
    created_at: datetime
    updated_at: datetime

class EquipmentStatusUpdate(SQLModel):
    status: STATUS
