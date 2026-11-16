from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.models.equipment import EquipmentTable
from app.models.issue import IssueTable
from app.schemas.common import utc_now
from app.schemas.issue import STATUS, IssueAssign, IssueIn, IssueOut, IssueStatusUpdate, Severity
from app.services import issue_service

router = APIRouter(prefix="/issues", tags=["issues"])


async def get_issue_or_404(issue_id: UUID, db: AsyncSession = Depends(get_db)) -> IssueTable:
    issue = await db.get(IssueTable, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.post("", response_model=IssueOut, status_code=201)
async def report_issue(issue: IssueIn, db: AsyncSession = Depends(get_db)):
    # Check the parent first: a bad equipment_id is the client's mistake (404), not a server error.
    if await db.get(EquipmentTable, issue.equipment_id) is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    new_issue = IssueTable.model_validate(issue)
    db.add(new_issue)
    await db.commit()
    await db.refresh(new_issue)
    return new_issue


@router.get("", response_model=List[IssueOut])
async def list_issues(
    db: AsyncSession = Depends(get_db),
    status: Optional[STATUS] = None,
    severity: Optional[Severity] = None,
    equipment_id: Optional[UUID] = None,
    assigned_to: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    statement = select(IssueTable)
    if status is not None:
        statement = statement.where(IssueTable.status == status)
    if severity is not None:
        statement = statement.where(IssueTable.severity == severity)
    if equipment_id is not None:
        statement = statement.where(IssueTable.equipment_id == equipment_id)
    if assigned_to is not None:
        statement = statement.where(IssueTable.assigned_to == assigned_to)
    statement = statement.order_by(IssueTable.created_at.desc()).offset(offset).limit(limit)  # type: ignore[union-attr]
    return (await db.execute(statement)).scalars().all()


@router.get("/critical", response_model=List[IssueOut])
async def list_critical_issues(db: AsyncSession = Depends(get_db)):
    """Dashboard feed: critical issues nobody has resolved yet (Open or In Progress), oldest first."""
    statement = (
        select(IssueTable)
        .where(IssueTable.severity == Severity.CRITICAL)
        .where(IssueTable.status.in_(issue_service.UNRESOLVED))  # type: ignore[attr-defined]
        .order_by(IssueTable.created_at)
    )
    return (await db.execute(statement)).scalars().all()


@router.get("/{issue_id}", response_model=IssueOut)
async def get_issue(issue: IssueTable = Depends(get_issue_or_404)):
    return issue


@router.patch("/{issue_id}/status", response_model=IssueOut)
async def change_issue_status(
    body: IssueStatusUpdate,
    issue: IssueTable = Depends(get_issue_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        issue_service.change_status(issue, body.status)
    except issue_service.InvalidTransition as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    await db.refresh(issue)
    return issue


@router.patch("/{issue_id}/assign", response_model=IssueOut)
async def assign_issue(
    body: IssueAssign,
    issue: IssueTable = Depends(get_issue_or_404),
    db: AsyncSession = Depends(get_db),
):
    issue.assigned_to = body.assigned_to
    issue.updated_at = utc_now()
    await db.commit()
    await db.refresh(issue)
    return issue
