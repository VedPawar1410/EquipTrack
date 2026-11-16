from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.dependencies import get_equipment_or_404
from app.models.equipment import EquipmentTable
from app.schemas.common import utc_now
from app.schemas.equipment import STATUS, EquipmentIn, EquipmentOut, EquipmentStatusUpdate, EquipmentType

router = APIRouter(prefix="/equipment", tags=["equipment"])


async def _commit_or_409(db: AsyncSession, serial_number: str) -> None:
    """serial_number is UNIQUE in the database; turn the violation into a clear 409."""
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Equipment with serial_number '{serial_number}' already exists")


@router.post("", response_model=EquipmentOut, status_code=201)
async def create_equipment(equipment: EquipmentIn, db: AsyncSession = Depends(get_db)):
    new_equipment = EquipmentTable.model_validate(equipment)
    db.add(new_equipment)
    await _commit_or_409(db, equipment.serial_number)
    await db.refresh(new_equipment)
    return new_equipment


@router.get("", response_model=List[EquipmentOut])
async def list_equipment(
    db: AsyncSession = Depends(get_db),
    status: Optional[STATUS] = None,
    department: Optional[str] = None,
    equipment_type: Optional[EquipmentType] = Query(default=None, alias="type"),
    search: Optional[str] = Query(default=None, description="Case-insensitive partial match on name"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """An empty result is a normal answer (200 with []), not a 404: the collection exists."""
    statement = select(EquipmentTable)
    if status is not None:
        statement = statement.where(EquipmentTable.status == status)
    if department is not None:
        statement = statement.where(EquipmentTable.department == department)
    if equipment_type is not None:
        statement = statement.where(EquipmentTable.equipment_type == equipment_type)
    if search:
        statement = statement.where(EquipmentTable.name.ilike(f"%{search}%"))  # type: ignore[union-attr]
    statement = statement.order_by(EquipmentTable.created_at.desc()).offset(offset).limit(limit)  # type: ignore[union-attr]
    return (await db.execute(statement)).scalars().all()


@router.get("/{equipment_id}", response_model=EquipmentOut)
async def get_equipment(equipment: EquipmentTable = Depends(get_equipment_or_404)):
    return equipment


@router.get("/{equipment_id}/summary", response_model=EquipmentOut)
async def get_equipment_summary(equipment: EquipmentTable = Depends(get_equipment_or_404)):
    # TODO(step 9): full snapshot (recent logs, open issues, parts, documents, health score)
    return equipment


@router.put("/{equipment_id}", response_model=EquipmentOut)
async def update_equipment(
    changes: EquipmentIn,
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    equipment.sqlmodel_update(changes.model_dump())
    equipment.updated_at = utc_now()
    await _commit_or_409(db, changes.serial_number)
    await db.refresh(equipment)
    return equipment


@router.patch("/{equipment_id}/status", response_model=EquipmentOut)
async def update_equipment_status(
    body: EquipmentStatusUpdate,
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    equipment.status = body.status
    equipment.updated_at = utc_now()
    await db.commit()
    await db.refresh(equipment)
    return equipment


@router.delete("/{equipment_id}", status_code=204)
async def retire_equipment(
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete: the machine is retired but its maintenance history is kept."""
    equipment.status = STATUS.RETIRED
    equipment.updated_at = utc_now()
    await db.commit()
    return Response(status_code=204)


@router.delete("/{equipment_id}/hard", status_code=204)
async def hard_delete_equipment(
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Permanent delete. Logs, issues and parts go with it (ON DELETE CASCADE); documents are kept (SET NULL)."""
    await db.delete(equipment)
    await db.commit()
    return Response(status_code=204)
