from fastapi import APIRouter, Depends, HTTPException
from langchain_core.runnables import Runnable
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_equipment_or_404, limit_ai_requests
from app.models.equipment import EquipmentTable
from app.schemas.ai import AIAnswer, AskRequest, DiagnoseRequest
from app.services import ai_service
from app.services.llm import get_chat_model

# Every role may ask: answering questions about the manuals is the technician's core use case.
# limit_ai_requests depends on get_current_user, so this also requires a signed-in user.
router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(limit_ai_requests)])


@router.post("/ask", response_model=AIAnswer)
async def ask(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    chat: Runnable | None = Depends(get_chat_model),
):
    """Answer a free-form question from the uploaded manuals, with numbered citations."""
    if body.equipment_id is not None and await db.get(EquipmentTable, body.equipment_id) is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return await ai_service.ask(db, chat, body.question, body.equipment_id)


@router.post("/diagnose/{equipment_id}", response_model=AIAnswer)
async def diagnose(
    body: DiagnoseRequest,
    equipment: EquipmentTable = Depends(get_equipment_or_404),
    db: AsyncSession = Depends(get_db),
    chat: Runnable | None = Depends(get_chat_model),
):
    """Likely cause and next steps for a symptom, using the machine's history, open issues and manuals."""
    return await ai_service.diagnose(db, chat, equipment, body.symptom)
