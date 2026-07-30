from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.dependencies import get_equipment_or_404
from app.models.equipment import EquipmentTable
from app.models.part import PartTable
from app.schemas.part import PartIn, PartOut


router = APIRouter()

@router.post("/equipment/{equipment_id}/parts", response_model=PartOut, status_code=201, tags=["parts"])
async def create_part(
    part: PartIn,
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    new_part = PartTable(
        equipment_id=equipment.id,
        part_name=part.part_name,
        part_number=part.part_number,
        quantity_in_stock=part.quantity_in_stock,
        reorder_threshold=part.reorder_threshold,
        unit_cost_usd=part.unit_cost_usd,
        supplier=part.supplier,
    )
    db.add(new_part)
    await db.commit()
    
    await db.refresh(new_part)
    return new_part


@router.get("/equipment/{equipment_id}/parts", response_model=List[PartOut], status_code=200, tags=["parts"])
async def get_parts(
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
):
    statement = select(PartTable).where(PartTable.equipment_id == equipment.id)

    result = await db.execute(statement)
    parts = result.scalars().all()

    if not parts:
        raise HTTPException(status_code=404, detail="No parts found")

    return parts




@router.get("/parts/low-stock", response_model=List[PartOut], status_code=200, tags=["parts"])
async def get_low_stock_parts(
    db: AsyncSession = Depends(get_db),
):  
    statement = select(PartTable).where(PartTable.quantity_in_stock <= PartTable.reorder_threshold)
    result = await db.execute(statement)
    parts = result.scalars().all()
    if not parts:
        raise HTTPException(status_code=404, detail="No such parts found")
    return parts


@router.get("/parts/{id}", response_model=PartOut, status_code=200, tags=["parts"])
async def get_part(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    part = await db.get(PartTable, id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return part


@router.patch("/parts/{id}/quantity", response_model=PartOut, status_code=200, tags=["parts"])
async def update_part_quantity(
    id: UUID,
    quantity: int,
    db: AsyncSession = Depends(get_db),
):
    part = await db.get(PartTable, id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    current_quantity = part.quantity_in_stock

    if quantity < 0: #client is trying to subtract quantity
        if current_quantity - (-quantity) < 0:
            raise HTTPException(status_code=400, detail="Quantity is going below zero, please maintain positive quantity")
        current_quantity = current_quantity - (-quantity)

    else:
        current_quantity = current_quantity + quantity

    part.quantity_in_stock = current_quantity

    await db.commit()
    await db.refresh(part)
    return part


