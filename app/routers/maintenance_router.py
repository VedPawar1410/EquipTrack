from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import between, select

from app.core.database import get_db
from app.dependencies import get_equipment_or_404
from app.models.equipment import EquipmentTable
from app.models.maintenance import MaintainanceTable
from app.schemas.maintenance import MaintainanceIn, MaintainanceOut


router = APIRouter()

@router.post("/equipment/{equipment_id}/maintenance", response_model=MaintainanceOut, status_code=201, tags=["maintenance"])
async def create_maintainance(
    maintenance: MaintainanceIn,
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    new_maintainance = MaintainanceTable(
        equipment_id=equipment.id,
        log_type=maintenance.log_type,
        performed_by=maintenance.performed_by,
        performed_at=maintenance.performed_at,
        description=maintenance.description,
        duration_minutes=maintenance.duration_minutes,
        cost_usd=maintenance.cost_usd,
        next_scheduled_at=maintenance.next_scheduled_at,
    )
    db.add(new_maintainance)
    await db.commit()
    # I want to put a check to make sure that the log type is in the correct format
    await db.refresh(new_maintainance)
    return new_maintainance


@router.get("/equipment/{equipment_id}/maintenance", response_model=List[MaintainanceOut], status_code=200, tags=["maintenance"])
async def get_maintainance_logs(
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    statement = (
        select(MaintainanceTable)
        .where(MaintainanceTable.equipment_id == equipment.id)
    )
    result = await db.execute(statement)

    return result.scalars().all()

@router.get("/maintenance/upcoming", response_model=List[MaintainanceOut], status_code=200, tags=["maintenance"])
async def get_upcoming_maintainance_logs(
    db: AsyncSession = Depends(get_db), 
):
    # 1. Get today's date and the 30-day cutoff date as strings (YYYY-MM-DD)
    today = datetime.now().date()
    cutoff = today + timedelta(days=30) # YYYY-MM-DD

    # 2. Build the statement matching only the first 10 characters of your data
    statement = (
        select(MaintainanceTable)
        .where(
            between(MaintainanceTable.next_scheduled_at, today, cutoff)
        )
    )
    result = await db.execute(statement)

    return result.scalars().all()

@router.get("/maintenance/{log_id}", response_model=MaintainanceOut, status_code=200, tags=["maintenance"])
async def get_maintainance_log_by_id(
    log_id: UUID,
    db: AsyncSession = Depends(get_db), 
):
    maintenance = await db.get(MaintainanceTable, log_id)

    if not maintenance:
        raise HTTPException(status_code=404, detail="Maintenance log not found")    
    return maintenance


