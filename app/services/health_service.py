"""Equipment health score: a pure function of facts, so it is trivial to unit-test.

Formula (from the project spec):
  start at 100
  -10 per open Medium issue, -20 per open High, -35 per open Critical (Low costs nothing)
  -15 if the last maintenance was more than 6 months ago (or there is none on record)
  -20 if the next scheduled maintenance is in the past (overdue)
  floor at 0
"Open" means unresolved: Open or In Progress.
"""
from collections import Counter
from datetime import datetime, timedelta

from app.schemas.analytics import HealthBand, HealthDeduction, HealthScore
from app.schemas.issue import Severity

ISSUE_PENALTY = {Severity.CRITICAL: 35, Severity.HIGH: 20, Severity.MEDIUM: 10, Severity.LOW: 0}
STALE_AFTER = timedelta(days=182)   # ~6 months
STALE_PENALTY = 15
OVERDUE_PENALTY = 20


def band_for(score: int) -> HealthBand:
    if score >= 80:
        return HealthBand.GOOD
    return HealthBand.FAIR if score >= 50 else HealthBand.POOR


def compute_health(
    open_issue_severities: list[Severity | str],
    last_maintenance_at: datetime | None,
    next_scheduled_at: datetime | None,
    now: datetime,
) -> HealthScore:
    deductions: list[HealthDeduction] = []

    counts = Counter(Severity(s) for s in open_issue_severities)
    for severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM):
        if counts[severity]:
            deductions.append(HealthDeduction(
                reason=f"{counts[severity]} open {severity.value} issue(s)",
                points=counts[severity] * ISSUE_PENALTY[severity],
            ))

    if last_maintenance_at is None:
        deductions.append(HealthDeduction(reason="No maintenance on record", points=STALE_PENALTY))
    elif now - last_maintenance_at > STALE_AFTER:
        days = (now - last_maintenance_at).days
        deductions.append(HealthDeduction(reason=f"Last maintenance {days} days ago", points=STALE_PENALTY))

    if next_scheduled_at is not None and next_scheduled_at < now:
        days = (now - next_scheduled_at).days
        deductions.append(HealthDeduction(reason=f"Scheduled maintenance overdue by {days} day(s)",
                                          points=OVERDUE_PENALTY))

    score = max(0, 100 - sum(d.points for d in deductions))
    return HealthScore(score=score, band=band_for(score), deductions=deductions)
