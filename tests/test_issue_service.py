"""Pure unit tests of the issue rules: no database, no HTTP. This is what the service layer buys."""
from itertools import product
from uuid import uuid4

import pytest

from app.models.issue import IssueTable
from app.models.user import UserTable
from app.schemas.issue import STATUS, Severity
from app.schemas.user import Role
from app.services import issue_service
from app.services.auth_service import NotPermitted

ALLOWED = {(STATUS.OPEN, STATUS.INPROGRESS), (STATUS.INPROGRESS, STATUS.RESOLVED),
           (STATUS.RESOLVED, STATUS.CLOSED), (STATUS.RESOLVED, STATUS.INPROGRESS)}


def make_issue(status):
    return IssueTable(equipment_id=uuid4(), title="t", severity=Severity.LOW, reported_by="x", status=status)


def make_user(role):
    return UserTable(id=uuid4(), username=role.value, email=f"{role.value}@x.io", role=role, hashed_password="h")


@pytest.mark.parametrize("current, target", list(product(STATUS, STATUS)))
def test_transition_table(current, target):
    issue = make_issue(current)
    if (current, target) in ALLOWED:
        assert issue_service.change_status(issue, target, make_user(Role.ADMIN)).status == target
    else:
        with pytest.raises(issue_service.InvalidTransition):
            issue_service.change_status(issue, target, make_user(Role.ADMIN))


@pytest.mark.parametrize("current, target", [(STATUS.RESOLVED, STATUS.CLOSED), (STATUS.RESOLVED, STATUS.INPROGRESS)])
def test_supervisor_only_transitions(current, target):
    with pytest.raises(NotPermitted):
        issue_service.change_status(make_issue(current), target, make_user(Role.TECHNICIAN))
    assert issue_service.change_status(make_issue(current), target, make_user(Role.SUPERVISOR)).status == target


def test_claim_does_not_steal_an_existing_assignment():
    issue = make_issue(STATUS.OPEN)
    issue.assigned_to, issue.assigned_to_id = "someone", uuid4()
    issue_service.change_status(issue, STATUS.INPROGRESS, make_user(Role.TECHNICIAN))
    assert issue.assigned_to == "someone"
