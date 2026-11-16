from datetime import datetime
from typing import List, TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship

from app.models.equipment import EquipmentTable
from app.schemas.document import DOCTYPE, DocumentShared

class DocumentTable(DocumentShared, table=True):
    __tablename__ = "documents"  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    equipment_id: Optional[UUID] = Field(default=None, foreign_key="equipment.id")  # nullable: general documents
    uploaded_by: Optional[str] = Field(default=None, max_length=100)

    # Connects back to the parent table for ORM usage
    equipment: Optional[EquipmentTable] = Relationship(back_populates="documents")  