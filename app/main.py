from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.routers.equipment_router import router as endpoints_router
from app.routers.issue_router import router as issue_router
from app.routers.maintenance_router import router as maintenance_router
from app.routers.parts_router import router as part_router

app = FastAPI(
    title="EquipTrack API",
    description="Manufacturing equipment maintenance: equipment, maintenance logs, issues and spare parts.",
    version="0.1.0",
)

app.include_router(endpoints_router, prefix="/api/v1")
app.include_router(maintenance_router, prefix="/api/v1")
app.include_router(issue_router, prefix="/api/v1")
app.include_router(part_router, prefix="/api/v1")


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Safety net: a constraint the routes didn't pre-check becomes a 409 with the usual
    {"detail": ...} shape instead of a 500 with a stack trace."""
    return JSONResponse(status_code=409, content={"detail": "Request conflicts with existing data or constraints"})


@app.get("/", tags=["meta"])
def read_root():
    return {"name": "EquipTrack API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["meta"])
async def health(db: AsyncSession = Depends(get_db)):
    """Liveness + DB connectivity check, used by Docker/hosting platforms and uptime monitors."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok", "database": "ok"}
