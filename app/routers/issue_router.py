from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.models.issue import IssueTable
from app.schemas.issue import STATUS, IssueIn, IssueOut, Severity

router = APIRouter()

@router.post("/issues", response_model=IssueOut, status_code=201, tags=["issues"])
async def create_issue(
    issue: IssueIn,
    db: AsyncSession = Depends(get_db),
): 
    new_issue = IssueTable(
        title=issue.title,
        description=issue.description,
        severity=issue.severity,
        reported_by=issue.reported_by,
        error_code=issue.error_code,
        equipment_id=issue.equipment_id,
    )
    db.add(new_issue)
    await db.commit()
    # I want to put a check to make sure that the log type is in the correct format
    await db.refresh(new_issue)
    return new_issue


@router.get("/issues", response_model=List[IssueOut], status_code=200, tags=["issues"])
async def get_issues(
    db: AsyncSession = Depends(get_db), 
    status: Optional[STATUS] = None,
    severity: Optional[Severity] = None,
    equipment_id: Optional[UUID] = None,
    assigned_to: Optional[str] = None,
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

    result = await db.execute(statement)
    issues = result.scalars().all()

    if not issues:
        raise HTTPException(status_code=404, detail="No issues found")

    return issues


@router.get("/issues/critical", response_model=List[IssueOut], status_code=200, tags=["issues"])
async def get_critical_issues(
    db: AsyncSession = Depends(get_db), 
):
    statement = select(IssueTable).where(IssueTable.severity == Severity.CRITICAL).where(IssueTable.status == STATUS.OPEN)

    result = await db.execute(statement)
    issues = result.scalars().all()

    if not issues:
        raise HTTPException(status_code=404, detail="No critical issues found")

    return issues



@router.get("/issues/{id}", response_model=IssueOut, status_code=200, tags=["issues"])
async def get_issue_by_id(
    id: UUID,
    db: AsyncSession = Depends(get_db), 
):
    issue = await db.get(IssueTable, id)

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")    
    
    return issue


@router.patch("/issues/{id}/status", response_model=IssueOut, status_code=200, tags=["issues"])
async def update_issue_status(
    id: UUID,
    status: Optional[STATUS] = None,
    db: AsyncSession = Depends(get_db),
):
    update_issue = await db.get(IssueTable, id)
    if not update_issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    #the user wants to update the status of the issue. But if the issue they are trying to update is closed, they cant update it anymore.
    #if the issue is in progress, you cant go back to open, you can only go to resolved or closed.
    # if you are in resolved, you cant go back to open, you can only go to closed or back to in progress, if the fix wasnt done properly after a review.
    if update_issue.status == STATUS.CLOSED and status != STATUS.OPEN: # i am putting this condition for status open becuase i can test in my development environment, later will change this.
        raise HTTPException(status_code=400, detail="You cant update a closed issue, please create a new issue instead")
    if update_issue.status == STATUS.INPROGRESS and status == STATUS.CLOSED:
        raise HTTPException(status_code=400, detail="You cant update an in progress issue directly to closed, it needs to be resolved first")
    if update_issue.status == STATUS.RESOLVED and status == STATUS.OPEN:
        raise HTTPException(status_code=400, detail="You cant update a resolved issue to open, it can only be closed or be set to 'in progress'")

    if status is not None:
        update_issue.status = status
        
    await db.commit()
    await db.refresh(update_issue)    
    return update_issue


@router.patch("/issues/{id}/assign", response_model=IssueOut, status_code=200, tags=["issues"])
async def update_issue_assign(
    id: UUID,
    assigned_to: str,
    db: AsyncSession = Depends(get_db),
):
    update_issue = await db.get(IssueTable, id)
    if not update_issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    update_issue.assigned_to = assigned_to

    await db.commit()
    await db.refresh(update_issue)  
    return update_issue