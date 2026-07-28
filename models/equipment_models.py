from sqlmodel import SQLModel
from datetime import date, datetime
from uuid import UUID, uuid4
from sqlmodel import Field
from enum import Enum
from sqlalchemy import Enum as SAEnum


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

class SharedEquipment(SQLModel):
    name: str
    model_number: str | None = None
    serial_number: str
    # This keeps validation in Python, but saves as standard VARCHAR in Postgres
    # https://share.google/aimode/5s3vd8NgXmbcTjTVj
    equipment_type: EquipmentType = Field(
        sa_type=SAEnum(EquipmentType, native_enum=False, create_type=False) # type: ignore
    )
    location: str
    department: str
    purchased_at: date
    warranty_expires_at: date

    # model_config = ConfigDict
    # FIX: Use standard class Config for SQLModel compatibility
    # https://share.google/aimode/1Ceh5MsCNGSADmlGW
    class Config:
        json_schema_extra={
            "example": {
                "name": "Robotic Arm Alpha",
                "model_number": "RA-2000-X",
                "serial_number": "SN-987654321",
                "equipment_type": "Robotic Arm",  # Matches the Enum value
                "location": "Bay 4, Assembly Line A",
                "department": "Body Shop",
                "purchased_at": "2026-01-15",# ISO format date strings
                "warranty_expires_at": "2031-01-15"
            }
        }

class EquipmentIn(SharedEquipment):
    pass
    

class EquipmentOut(SharedEquipment):
    id: UUID
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class EquipmentTable(SharedEquipment, table=True):
    __tablename__ = "equipment" # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    

