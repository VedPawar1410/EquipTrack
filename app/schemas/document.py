from sqlmodel import SQLModel
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from sqlmodel import Field
from enum import Enum
from sqlalchemy import Enum as SAEnum
from typing import List, Optional
from sqlmodel import Relationship


class DOCTYPE(str, Enum):
    MANUAL = "Manual"
    SERVICE_MANUAL = "Service Manual"
    SOP = "SOP"
    INSTALLATION_GUIDE = "Installation Guide"
 
    # Safety & compliance
    SAFETY_GUIDE = "Safety Guide"
    MSDS = "MSDS"
    LOCKOUT_TAGOUT = "Lockout/Tagout Procedure"
 
    # Technical reference
    DATASHEET = "Datasheet"
    WIRING_DIAGRAM = "Wiring Diagram"
    PARTS_CATALOG = "Parts Catalog"
    ERROR_CODE_REFERENCE = "Error Code Reference"
    TROUBLESHOOTING_GUIDE = "Troubleshooting Guide"
 
    # Certificates & checklists
    CALIBRATION_CERTIFICATE = "Calibration Certificate"
    INSPECTION_CHECKLIST = "Inspection Checklist"

    OTHER = "Other"



class DocumentShared(SQLModel):
    title: str = Field(max_length=100)
    blob_url: str
    doc_type: DOCTYPE = Field(
        sa_type=SAEnum(DOCTYPE, native_enum=False, create_type=False,
        values_callable=lambda enum_cls: [e.value for e in enum_cls]) # type: ignore
    )
    file_size_bytes: int | None = None
    is_indexed: bool = False
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DocumentIn(DocumentShared):
    equipment_id: UUID | None = None  # None = general document (e.g. a plant-wide safety guide)

class DocumentOut(DocumentShared):
    id: UUID
    equipment_id: UUID | None = None
    uploaded_by: str | None = None          