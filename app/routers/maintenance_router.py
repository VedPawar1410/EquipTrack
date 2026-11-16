from datetime import datetime, time, timedelta, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.dependencies import get_current_user, get_equipment_or_404
from app.models.equipment import EquipmentTable
from app.models.maintenance import MaintenanceTable
from app.models.user import UserTable
from app.schemas.maintenance import MaintenanceIn, MaintenanceOut

router = APIRouter(tags=["maintenance"], dependencies=[Depends(get_current_user)])


@router.post("/equipment/{equipment_id}/maintenance", response_model=MaintenanceOut, status_code=201)
async def log_maintenance(
    maintenance: MaintenanceIn,
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    user: UserTable = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = maintenance.model_dump()
    data["performed_by"] = data["performed_by"] or user.username
    log = MaintenanceTable(equipment_id=equipment.id, performed_by_id=user.id, **data)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.get("/equipment/{equipment_id}/maintenance", response_model=List[MaintenanceOut])
async def list_maintenance_logs(
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    """The machine's health history, newest first."""
    statement = (
        select(MaintenanceTable)
        .where(MaintenanceTable.equipment_id == equipment.id)
        .order_by(MaintenanceTable.performed_at.desc())  # type: ignore[attr-defined]
    )
    return (await db.execute(statement)).scalars().all()


@router.get("/maintenance/upcoming", response_model=List[MaintenanceOut])
async def list_upcoming_maintenance(db: AsyncSession = Depends(get_db)):
    # next_scheduled_at is TIMESTAMPTZ, so compare against timezone-aware datetimes.
    # Window: from the start of today (UTC) up to, not including, the start of day 31.
    start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=31)
    statement = (
        select(MaintenanceTable)
        .where(MaintenanceTable.next_scheduled_at >= start)  # type: ignore[operator]
        .where(MaintenanceTable.next_scheduled_at < end)  # type: ignore[operator]
        .order_by(MaintenanceTable.next_scheduled_at)
    )
    return (await db.execute(statement)).scalars().all()


@router.get("/maintenance/{log_id}", response_model=MaintenanceOut)
async def get_maintenance_log(log_id: UUID, db: AsyncSession = Depends(get_db)):
    log = await db.get(MaintenanceTable, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Maintenance log not found")
    return log
