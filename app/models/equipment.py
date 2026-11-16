from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship

from app.schemas.equipment import STATUS, SharedEquipment

if TYPE_CHECKING:
    from app.models.issue import IssueTable
    from app.models.maintenance import MaintenanceTable
    from app.models.part import PartTable
    from app.models.document import DocumentTable


class EquipmentTable(SharedEquipment, table=True):
    __tablename__ = "equipment"  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    status: STATUS = Field(
        default=STATUS.ACTIVE,
        sa_type=SAEnum(STATUS, native_enum=False, create_type=False,
        values_callable=lambda enum_cls: [e.value for e in enum_cls])  # type: ignore
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Children are removed (CASCADE) or detached (SET NULL) by the database's foreign keys.
    # passive_deletes="all" stops SQLAlchemy from trying to NULL the child FKs itself, which
    # failed on NOT NULL columns and made hard-delete a 500.
    maintenance_logs: List["MaintenanceTable"] = Relationship(back_populates="equipment", passive_deletes="all")
    issues: List["IssueTable"] = Relationship(back_populates="equipment", passive_deletes="all")
    parts: List["PartTable"] = Relationship(back_populates="equipment", passive_deletes="all")
    documents: List["DocumentTable"] = Relationship(back_populates="equipment", passive_deletes="all")
