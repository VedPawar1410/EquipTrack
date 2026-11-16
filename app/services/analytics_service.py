"""Read-side queries for the summary, health and dashboard endpoints."""
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlmodel import select

from app.models.document import DocumentTable
from app.models.equipment import EquipmentTable
from app.models.issue import IssueTable
from app.models.maintenance import MaintenanceTable
from app.models.part import PartTable
from app.schemas.analytics import Dashboard, EquipmentHealth, EquipmentSummary, HealthBand
from app.schemas.common import utc_now
from app.schemas.equipment import STATUS as EquipmentStatus
from app.schemas.issue import Severity
from app.services.health_service import compute_health
from app.services.issue_service import UNRESOLVED


def latest_log_per_machine():
    """One row per machine: its most recent maintenance log (Postgres DISTINCT ON).

    Only the latest log's next_scheduled_at is the machine's current plan; older logs'
    plans were superseded when the machine was serviced again.
    Served by idx_maintenance_equip_performed (equipment_id, performed_at DESC).
    """
    latest = (
        select(MaintenanceTable)
        .ext(distinct_on(MaintenanceTable.equipment_id))
        .order_by(MaintenanceTable.equipment_id,
                  MaintenanceTable.performed_at.desc(),  # type: ignore[attr-defined]
                  MaintenanceTable.created_at.desc())    # type: ignore[attr-defined]
        .subquery()
    )
    return aliased(MaintenanceTable, latest)


def next_30_days_window() -> tuple[datetime, datetime]:
    """From the start of today (UTC) up to, not including, the start of day 31."""
    start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=31)


def _not_retired(log_alias):
    return log_alias.equipment_id.in_(
        select(EquipmentTable.id).where(EquipmentTable.status != EquipmentStatus.RETIRED)
    )


async def upcoming_maintenance(db: AsyncSession) -> list[MaintenanceTable]:
    latest = latest_log_per_machine()
    start, end = next_30_days_window()
    statement = (
        select(latest)
        .where(latest.next_scheduled_at >= start, latest.next_scheduled_at < end)
        .where(_not_retired(latest))
        .order_by(latest.next_scheduled_at)
    )
    return list((await db.execute(statement)).scalars().all())


async def equipment_summary(db: AsyncSession, equipment: EquipmentTable) -> EquipmentSummary:
    async def all_of(statement):
        return list((await db.execute(statement)).scalars().all())

    recent = await all_of(
        select(MaintenanceTable).where(MaintenanceTable.equipment_id == equipment.id)
        .order_by(MaintenanceTable.performed_at.desc(), MaintenanceTable.created_at.desc())  # type: ignore[attr-defined]
        .limit(5)
    )
    open_issues = await all_of(
        select(IssueTable).where(IssueTable.equipment_id == equipment.id)
        .where(IssueTable.status.in_(UNRESOLVED)).order_by(IssueTable.created_at)  # type: ignore[attr-defined]
    )
    parts = await all_of(select(PartTable).where(PartTable.equipment_id == equipment.id).order_by(PartTable.part_name))
    documents = await all_of(
        select(DocumentTable).where(DocumentTable.equipment_id == equipment.id).order_by(DocumentTable.title)
    )
    latest = recent[0] if recent else None
    health = compute_health(
        [i.severity for i in open_issues],
        latest.performed_at if latest else None,
        latest.next_scheduled_at if latest else None,
        now=utc_now(),
    )
    return EquipmentSummary(
        equipment=equipment, health=health, recent_maintenance=recent, open_issues=open_issues,
        parts=parts, low_stock_parts=sum(p.quantity_in_stock <= p.reorder_threshold for p in parts),
        documents=documents,
    )


async def health_for_all(db: AsyncSession) -> list[EquipmentHealth]:
    """Health for every non-retired machine in 3 queries total (not 3 per machine: no N+1)."""
    machines_q = select(EquipmentTable).where(EquipmentTable.status != EquipmentStatus.RETIRED)
    machines = list((await db.execute(machines_q)).scalars().all())

    severities: dict[UUID, list[str]] = defaultdict(list)
    rows = await db.execute(select(IssueTable.equipment_id, IssueTable.severity)
                            .where(IssueTable.status.in_(UNRESOLVED)))  # type: ignore[attr-defined]
    for equipment_id, severity in rows:
        severities[equipment_id].append(severity)

    latest = latest_log_per_machine()
    last_logs = {log.equipment_id: log for log in (await db.execute(select(latest))).scalars().all()}

    now = utc_now()
    results = []
    for machine in machines:
        log = last_logs.get(machine.id)
        score = compute_health(severities[machine.id], log.performed_at if log else None,
                               log.next_scheduled_at if log else None, now)
        results.append(EquipmentHealth(equipment_id=machine.id, name=machine.name, **score.model_dump()))
    return results


async def dashboard(db: AsyncSession) -> Dashboard:
    # Counts are done by Postgres (GROUP BY), not by loading rows into Python.
    by_status = {s.value: 0 for s in EquipmentStatus}
    for status, count in await db.execute(
            select(EquipmentTable.status, func.count()).group_by(EquipmentTable.status)):
        by_status[EquipmentStatus(status).value] = count

    by_severity = {s.value: 0 for s in Severity}
    for severity, count in await db.execute(
            select(IssueTable.severity, func.count()).where(IssueTable.status.in_(UNRESOLVED))  # type: ignore[attr-defined]
            .group_by(IssueTable.severity)):
        by_severity[Severity(severity).value] = count

    latest = latest_log_per_machine()
    start, end = next_30_days_window()
    now = utc_now()
    due = (await db.execute(select(func.count()).select_from(latest).where(
        latest.next_scheduled_at >= start, latest.next_scheduled_at < end, _not_retired(latest)))).scalar_one()
    overdue = (await db.execute(select(func.count()).select_from(latest).where(
        latest.next_scheduled_at < now, _not_retired(latest)))).scalar_one()
    low_stock = (await db.execute(select(func.count()).select_from(PartTable).where(
        PartTable.quantity_in_stock <= PartTable.reorder_threshold))).scalar_one()

    attention = sorted((h for h in await health_for_all(db) if h.band != HealthBand.GOOD), key=lambda h: h.score)[:5]
    return Dashboard(
        equipment_by_status=by_status, open_issues_by_severity=by_severity,
        critical_open_issues=by_severity[Severity.CRITICAL.value], machines_due_next_30_days=due,
        machines_overdue=overdue, low_stock_parts=low_stock, needs_attention=attention,
    )
