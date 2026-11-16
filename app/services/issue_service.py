"""Issue business rules. Kept free of HTTP so they can be unit-tested without a server.

The router maps InvalidTransition -> 422 and NotPermitted -> 403; this module never imports FastAPI.
"""
from app.models.issue import IssueTable
from app.models.user import UserTable
from app.schemas.common import utc_now
from app.schemas.issue import STATUS
from app.schemas.user import Role
from app.services.auth_service import NotPermitted, has_role

# The issue lifecycle, and the minimum role for each step. Anything not listed is rejected.
#   Open -> In Progress -> Resolved -> Closed
#                 ^            |
#                 +------------+  (reopened: the fix didn't hold)
TRANSITIONS: dict[tuple[STATUS, STATUS], Role] = {
    (STATUS.OPEN, STATUS.INPROGRESS): Role.TECHNICIAN,      # claim it
    (STATUS.INPROGRESS, STATUS.RESOLVED): Role.TECHNICIAN,  # mark the fix done
    (STATUS.RESOLVED, STATUS.CLOSED): Role.SUPERVISOR,      # sign off
    (STATUS.RESOLVED, STATUS.INPROGRESS): Role.SUPERVISOR,  # reopen
}

UNRESOLVED = (STATUS.OPEN, STATUS.INPROGRESS)


class InvalidTransition(Exception):
    pass


def change_status(issue: IssueTable, new_status: STATUS, actor: UserTable) -> IssueTable:
    """Validate and apply a status change, keeping resolved_at / updated_at / assignee consistent."""
    current = STATUS(issue.status)
    min_role = TRANSITIONS.get((current, new_status))
    if min_role is None:
        raise InvalidTransition(f"Cannot transition from '{current.value}' to '{new_status.value}'")
    if not has_role(actor.role, min_role):
        raise NotPermitted(
            f"Only a {min_role.value} or above can move an issue from '{current.value}' to '{new_status.value}'"
        )

    now = utc_now()
    issue.status = new_status
    issue.updated_at = now
    if new_status == STATUS.RESOLVED:
        issue.resolved_at = now
    elif new_status == STATUS.INPROGRESS:
        issue.resolved_at = None  # reopened, so it is no longer resolved
        if current == STATUS.OPEN and issue.assigned_to_id is None:
            # Claiming an unassigned issue assigns it to whoever claimed it.
            issue.assigned_to, issue.assigned_to_id = actor.username, actor.id
    return issue
