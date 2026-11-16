from enum import Enum
from uuid import UUID

from sqlmodel import SQLModel

from app.schemas.document import DocumentOut
from app.schemas.equipment import EquipmentOut
from app.schemas.issue import IssueOut
from app.schemas.maintenance import MaintenanceOut
from app.schemas.part import PartOut


class HealthBand(str, Enum):
    GOOD = "good"   # 80-100
    FAIR = "fair"   # 50-79
    POOR = "poor"   # 0-49


class HealthDeduction(SQLModel):
    reason: str
    points: int


class HealthScore(SQLModel):
    """0-100, with every deduction listed, so a person (or the AI assistant) can see WHY."""
    score: int
    band: HealthBand
    deductions: list[HealthDeduction]


class EquipmentHealth(HealthScore):
    equipment_id: UUID
    name: str


class EquipmentSummary(SQLModel):
    """Everything the equipment detail page needs, in one request."""
    equipment: EquipmentOut
    health: HealthScore
    recent_maintenance: list[MaintenanceOut]   # last 5, newest first
    open_issues: list[IssueOut]                # Open or In Progress
    parts: list[PartOut]
    low_stock_parts: int
    documents: list[DocumentOut]


class Dashboard(SQLModel):
    equipment_by_status: dict[str, int]
    open_issues_by_severity: dict[str, int]    # unresolved only
    critical_open_issues: int
    machines_due_next_30_days: int
    machines_overdue: int
    low_stock_parts: int
    needs_attention: list[EquipmentHealth]     # lowest health first, below "good", max 5
