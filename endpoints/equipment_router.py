from uuid import UUID
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from models.equipment_models import EquipmentIn, EquipmentOut, EquipmentTable
from fastapi import APIRouter
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from typing import List
from sqlmodel import select
from models.equipment_models import STATUS, EquipmentType
from typing import Optional

# 1. Create a router instead of using 'app'
router = APIRouter()

@router.post("/equipment", response_model=EquipmentOut, status_code=201)
async def create_equipment(equipment: EquipmentIn, db: AsyncSession = Depends(get_db)):
    new_equipment = EquipmentTable(
        name=equipment.name,
        model_number=equipment.model_number,
        serial_number=equipment.serial_number,
        equipment_type=equipment.equipment_type,
        location=equipment.location,
        department=equipment.department,
        purchased_at=equipment.purchased_at,
        warranty_expires_at=equipment.warranty_expires_at,
    )
    db.add(new_equipment)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Equipment with serial_number '{equipment.serial_number}' already exists",
        )
    await db.refresh(new_equipment)
    return new_equipment
    

@router.get("/equipment", response_model=List[EquipmentOut], status_code=200)
async def get_equipments(
    db: AsyncSession = Depends(get_db), 
    status: Optional[STATUS] = None, 
    department: str | None = None,
    type: Optional[EquipmentType] = None,
    search: Optional[str] | None = None
):
    statement = select(EquipmentTable)

    if status is not None:
        statement = statement.where(EquipmentTable.status == status)

    if department is not None:
        statement = statement.where(EquipmentTable.department == department)

    if type is not None:
        statement = statement.where(EquipmentTable.equipment_type == type)

    if search is not None:
        statement = statement.where(EquipmentTable.name.contains(search)) # type: ignore


    result = await db.execute(statement)
    equipments = result.scalars().all()

    if not equipments:
        raise HTTPException(status_code=404, detail="No equipment found")

    return equipments



@router.get("/equipment/{id}", response_model=EquipmentOut, status_code=200)
async def get_equipment_by_id(
    id: UUID,
    db: AsyncSession = Depends(get_db), 
):
    equipment = await db.get(EquipmentTable, id)

    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")    
    return equipment