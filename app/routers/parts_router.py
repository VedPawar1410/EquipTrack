from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.dependencies import get_current_user, get_equipment_or_404, require_role
from app.models.equipment import EquipmentTable
from app.models.part import PartTable
from app.models.user import UserTable
from app.schemas.part import PartIn, PartOut, PartQuantityChange
from app.schemas.user import Role
from app.services import parts_service
from app.services.auth_service import NotPermitted

router = APIRouter(tags=["parts"], dependencies=[Depends(get_current_user)])


@router.post("/equipment/{equipment_id}/parts", response_model=PartOut, status_code=201,
             dependencies=[Depends(require_role(Role.SUPERVISOR))])
async def add_part(
    part: PartIn,
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    new_part = PartTable(equipment_id=equipment.id, **part.model_dump())
    db.add(new_part)
    await db.commit()
    await db.refresh(new_part)
    return new_part


@router.get("/equipment/{equipment_id}/parts", response_model=List[PartOut])
async def list_parts(
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    statement = select(PartTable).where(PartTable.equipment_id == equipment.id).order_by(PartTable.part_name)
    return (await db.execute(statement)).scalars().all()


@router.get("/parts", response_model=List[PartOut])
async def list_all_parts(low_stock: bool = False, db: AsyncSession = Depends(get_db)):
    """The whole spare-parts inventory across machines (or only low-stock parts), lowest stock first."""
    statement = select(PartTable)
    if low_stock:
        statement = statement.where(PartTable.quantity_in_stock <= PartTable.reorder_threshold)
    statement = statement.order_by(PartTable.quantity_in_stock, PartTable.part_name)
    return (await db.execute(statement)).scalars().all()


@router.get("/parts/low-stock", response_model=List[PartOut])
async def list_low_stock_parts(db: AsyncSession = Depends(get_db)):
    """Parts at or below their reorder threshold (served by the partial index idx_parts_low_stock)."""
    statement = (
        select(PartTable)
        .where(PartTable.quantity_in_stock <= PartTable.reorder_threshold)
        .order_by(PartTable.quantity_in_stock)
    )
    return (await db.execute(statement)).scalars().all()


@router.get("/parts/{part_id}", response_model=PartOut)
async def get_part(part_id: UUID, db: AsyncSession = Depends(get_db)):
    part = await db.get(PartTable, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return part


@router.patch("/parts/{part_id}/quantity", response_model=PartOut)
async def change_part_quantity(
    part_id: UUID, body: PartQuantityChange,
    user: UserTable = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Technicians consume (negative); restocking (positive) needs a supervisor."""
    try:
        return await parts_service.adjust_stock(db, part_id, body.quantity_change, actor=user)
    except NotPermitted as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except parts_service.PartNotFound as exc:
        raise HTTPException(status_code=404, detail="Part not found") from exc
    except parts_service.InsufficientStock as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
