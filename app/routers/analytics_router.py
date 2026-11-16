from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_equipment_or_404, require_role
from app.models.equipment import EquipmentTable
from app.schemas.analytics import Dashboard, EquipmentHealth
from app.schemas.user import Role
from app.services import analytics_service

# Plant-wide analytics are supervisor-level (spec 17.5).
router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_role(Role.SUPERVISOR))])


@router.get("/dashboard", response_model=Dashboard)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    return await analytics_service.dashboard(db)


@router.get("/equipment/{equipment_id}/health", response_model=EquipmentHealth)
async def get_equipment_health(
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    summary = await analytics_service.equipment_summary(db, equipment)
    return EquipmentHealth(equipment_id=equipment.id, name=equipment.name, **summary.health.model_dump())
