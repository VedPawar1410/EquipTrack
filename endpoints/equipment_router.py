
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from models.equipment_models import EquipmentIn, EquipmentOut, EquipmentTable
from fastapi import APIRouter
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

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
    

