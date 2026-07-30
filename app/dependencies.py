from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.equipment import EquipmentTable


async def get_equipment_or_404(
    equipment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EquipmentTable:
    """Shared existence check for any route nested under /equipment/{equipment_id}/...

    Equipment, issues, maintenance logs, and parts all need this same check.
    Without it, every router repeats its own 404 lookup for the parent equipment.
    """
    equipment = await db.get(EquipmentTable, equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return equipment
