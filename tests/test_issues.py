import pytest

ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
async def issue(technician, equipment):
    response = await technician.post("/issues", json={
        "equipment_id": equipment["id"], "title": "Spindle vibration", "severity": "Critical", "error_code": "E-47",
    })
    assert response.status_code == 201
    return response.json()


async def move(client, issue, status):
    return await client.patch(f"/issues/{issue['id']}/status", json={"status": status})


async def test_reporter_is_the_logged_in_user(technician, users, equipment):
    body = (await technician.post("/issues", json={"equipment_id": equipment["id"], "title": "t", "severity": "Low",
                                                   "reported_by": "someone-else"})).json()
    assert body["reported_by"] == "tech" and body["reported_by_id"] == str(users["technician"].id)
    assert body["status"] == "Open"


async def test_unknown_equipment_is_404(technician, users):
    response = await technician.post("/issues", json={"equipment_id": ZERO, "title": "t", "severity": "Low"})
    assert response.status_code == 404


async def test_full_lifecycle_with_roles(technician, supervisor, users, issue):
    claimed = (await move(technician, issue, "In Progress")).json()
    assert claimed["assigned_to"] == "tech"                     # claiming assigns it to you
    resolved = (await move(technician, issue, "Resolved")).json()
    assert resolved["resolved_at"] is not None
    reopened = await move(supervisor, issue, "In Progress")
    assert reopened.status_code == 200 and reopened.json()["resolved_at"] is None
    await move(technician, issue, "Resolved")
    assert (await move(supervisor, issue, "Closed")).json()["status"] == "Closed"


@pytest.mark.parametrize("path", [["Closed"], ["Resolved"], ["Open"],
                                  ["In Progress", "Open"], ["In Progress", "Closed"]])
async def test_invalid_transitions_are_422(supervisor, issue, path):
    *setup, last = path
    for status in setup:
        assert (await move(supervisor, issue, status)).status_code == 200
    response = await move(supervisor, issue, last)
    assert response.status_code == 422 and "Cannot transition" in response.json()["detail"]


async def test_closed_is_terminal(technician, supervisor, issue):
    for client, status in [(technician, "In Progress"), (technician, "Resolved"), (supervisor, "Closed")]:
        await move(client, issue, status)
    for status in ("Open", "In Progress", "Resolved"):
        assert (await move(supervisor, issue, status)).status_code == 422


async def test_technician_cannot_close_or_reopen(technician, issue):
    await move(technician, issue, "In Progress")
    await move(technician, issue, "Resolved")
    assert (await move(technician, issue, "Closed")).status_code == 403
    assert (await move(technician, issue, "In Progress")).status_code == 403


async def test_assign_requires_supervisor_and_a_real_user(technician, supervisor, users, issue):
    assert (await technician.patch(f"/issues/{issue['id']}/assign", json={"assigned_to": "tech"})).status_code == 403
    assert (await supervisor.patch(f"/issues/{issue['id']}/assign", json={"assigned_to": "ghost"})).status_code == 422
    assert (await supervisor.patch(f"/issues/{issue['id']}/assign", json={"assigned_to": "gone"})).status_code == 422  # inactive
    body = (await supervisor.patch(f"/issues/{issue['id']}/assign", json={"assigned_to": "tech"})).json()
    assert body["assigned_to_id"] == str(users["technician"].id)


async def test_critical_feed_lists_only_unresolved_critical(technician, supervisor, equipment, issue):
    await technician.post("/issues", json={"equipment_id": equipment["id"], "title": "minor", "severity": "Low"})
    assert [i["id"] for i in (await technician.get("/issues/critical")).json()] == [issue["id"]]
    for client, status in [(technician, "In Progress"), (technician, "Resolved")]:
        await move(client, issue, status)
    assert (await technician.get("/issues/critical")).json() == []


async def test_filters(technician, issue):
    assert len((await technician.get("/issues?severity=Critical")).json()) == 1
    assert (await technician.get("/issues?status=Closed")).json() == []
    assert len((await technician.get(f"/issues?equipment_id={issue['equipment_id']}")).json()) == 1


async def test_get_unknown_is_404(technician):
    assert (await technician.get(f"/issues/{ZERO}")).status_code == 404


async def test_get_and_filter_by_assignee(technician, issue):
    await move(technician, issue, "In Progress")              # claim -> assigned to tech
    assert (await technician.get(f"/issues/{issue['id']}")).json()["assigned_to"] == "tech"
    assert len((await technician.get("/issues?assigned_to=tech")).json()) == 1
