from app.models.document import DocumentChunkTable, DocumentFileTable, DocumentTable
from app.models.equipment import EquipmentTable
from app.models.issue import IssueTable
from app.models.maintenance import MaintenanceTable
from app.models.part import PartTable
from app.models.user import UserTable

__all__ = [
    "EquipmentTable",
    "IssueTable",
    "MaintenanceTable",
    "PartTable",
    "DocumentTable",
    "DocumentFileTable",
    "DocumentChunkTable",
    "UserTable",
]
