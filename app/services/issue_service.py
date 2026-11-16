"""Issue business rules. Kept free of HTTP so they can be unit-tested without a server.

The router turns InvalidTransition into a 422; this module never imports FastAPI.
"""
from app.models.issue import IssueTable
from app.schemas.common import utc_now
from app.schemas.issue import STATUS

# The issue lifecycle. Anything not listed here is rejected.
#   Open -> In Progress -> Resolved -> Closed
#                 ^            |
#                 +------------+  (reopened: the fix didn't hold)
ALLOWED_TRANSITIONS: dict[STATUS, set[STATUS]] = {
    STATUS.OPEN: {STATUS.INPROGRESS},
    STATUS.INPROGRESS: {STATUS.RESOLVED},
    STATUS.RESOLVED: {STATUS.CLOSED, STATUS.INPROGRESS},
    STATUS.CLOSED: set(),  # terminal: report a new issue instead
}

UNRESOLVED = (STATUS.OPEN, STATUS.INPROGRESS)


class InvalidTransition(Exception):
    pass


def change_status(issue: IssueTable, new_status: STATUS) -> IssueTable:
    """Validate and apply a status change, keeping resolved_at and updated_at consistent."""
    current = STATUS(issue.status)
    if new_status not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"Cannot transition from '{current.value}' to '{new_status.value}'")

    now = utc_now()
    issue.status = new_status
    issue.updated_at = now
    if new_status == STATUS.RESOLVED:
        issue.resolved_at = now
    elif new_status == STATUS.INPROGRESS:
        issue.resolved_at = None  # reopened, so it is no longer resolved
    return issue
