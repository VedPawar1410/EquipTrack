from datetime import date, timedelta

import pytest

LOG = {"log_type": "Inspection", "description": "ok"}


async def issue(client, machine, severity):
    response = await client.post("/issues", json={"equipment_id": machine["id"], "title": severity, "severity": severity})
    return response.json()


async def test_summary_snapshot(technician, supervisor, equipment):
    eid = equipment["id"]
    for day in range(1, 8):                                       # 7 logs: summary keeps the newest 5
        await technician.post(f"/equipment/{eid}/maintenance", json={**LOG, "performed_at": f"2026-11-0{day}"})
    await technician.post(f"/equipment/{eid}/maintenance",
                          json={**LOG, "performed_at": str(date.today()), "next_scheduled_at": str(date.today() + timedelta(days=60))})
    high = await issue(technician, equipment, "High")
    closed = await issue(technician, equipment, "Low")
    for client, status in [(technician, "In Progress"), (technician, "Resolved"), (supervisor, "Closed")]:
        await client.patch(f"/issues/{closed['id']}/status", json={"status": status})
    await supervisor.post(f"/equipment/{eid}/parts", json={"part_name": "Fuse", "quantity_in_stock": 1, "reorder_threshold": 2})

    body = (await technician.get(f"/equipment/{eid}/summary")).json()
    assert body["equipment"]["id"] == eid
    assert len(body["recent_maintenance"]) == 5 and body["recent_maintenance"][0]["performed_at"].startswith(str(date.today()))
    assert [i["id"] for i in body["open_issues"]] == [high["id"]]   # the closed one is excluded
    assert body["low_stock_parts"] == 1 and body["documents"] == []
    assert body["health"] == {"score": 80, "band": "good",
                              "deductions": [{"reason": "1 open High issue(s)", "points": 20}]}


async def test_new_machine_with_no_history(technician, equipment):
    health = (await technician.get(f"/equipment/{equipment['id']}/summary")).json()["health"]
    assert health["score"] == 85 and health["deductions"][0]["reason"] == "No maintenance on record"


async def test_health_endpoint(supervisor, technician, equipment):
    await issue(technician, equipment, "Critical")
    body = (await supervisor.get(f"/analytics/equipment/{equipment['id']}/health")).json()
    assert body["name"] == equipment["name"] and body["score"] == 50 and body["band"] == "fair"


async def test_dashboard(supervisor, technician, admin, make_equipment):
    healthy, sick, overdue, retired = [await make_equipment() for _ in range(4)]
    today = date.today()
    await technician.post(f"/equipment/{healthy['id']}/maintenance",
                          json={**LOG, "performed_at": str(today), "next_scheduled_at": str(today + timedelta(days=10))})
    await technician.post(f"/equipment/{sick['id']}/maintenance",
                          json={**LOG, "performed_at": str(today), "next_scheduled_at": str(today + timedelta(days=90))})
    await issue(technician, sick, "Critical")
    await issue(technician, sick, "High")
    await technician.post(f"/equipment/{overdue['id']}/maintenance",
                          json={**LOG, "performed_at": str(today - timedelta(days=40)),
                                "next_scheduled_at": str(today - timedelta(days=5))})
    await admin.delete(f"/equipment/{retired['id']}")
    await supervisor.post(f"/equipment/{healthy['id']}/parts", json={"part_name": "Fuse", "quantity_in_stock": 0})

    body = (await supervisor.get("/analytics/dashboard")).json()
    assert body["equipment_by_status"] == {"active": 3, "under maintenance": 0, "retired": 1}
    assert body["open_issues_by_severity"] == {"Critical": 1, "High": 1, "Medium": 0, "Low": 0}
    assert body["critical_open_issues"] == 1
    assert body["machines_due_next_30_days"] == 1      # only `healthy`: sick's plan is 90 days out
    assert body["machines_overdue"] == 1
    assert body["low_stock_parts"] == 1
    # sick = 100 - 35 - 20 = 45 (poor). overdue = 100 - 20 = 80, still "good", so not listed. Retired never listed.
    assert [(m["equipment_id"], m["score"]) for m in body["needs_attention"]] == [(sick["id"], 45)]


@pytest.mark.parametrize("path", ["/analytics/dashboard", "/analytics/equipment/00000000-0000-0000-0000-000000000000/health"])
async def test_analytics_requires_supervisor(technician, path):
    assert (await technician.get(path)).status_code == 403


async def test_health_for_every_machine(technician, admin, make_equipment):
    sick, fine, retired = [await make_equipment() for _ in range(3)]
    await issue(technician, sick, "High")
    await admin.delete(f"/equipment/{retired['id']}")
    scores = {h["equipment_id"]: h["score"] for h in (await technician.get("/equipment/health")).json()}
    assert scores == {sick["id"]: 65, fine["id"]: 85}     # no logs on record (-15), High issue (-20); retired excluded
