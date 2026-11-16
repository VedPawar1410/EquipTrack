from datetime import date, timedelta

from app.schemas.common import utc_now

ZERO = "00000000-0000-0000-0000-000000000000"
LOG = {"log_type": "Scheduled", "performed_at": "2026-11-04T10:00:00Z", "description": "Lubrication service",
       "duration_minutes": 120, "cost_usd": 450.0}


async def test_log_defaults_performer_to_current_user(technician, users, equipment):
    response = await technician.post(f"/equipment/{equipment['id']}/maintenance", json=LOG)
    assert response.status_code == 201
    body = response.json()
    assert body["performed_by"] == "tech" and body["performed_by_id"] == str(users["technician"].id)
    assert body["equipment_id"] == equipment["id"]


async def test_log_for_contractor_keeps_name_and_records_account(technician, users, equipment):
    body = (await technician.post(f"/equipment/{equipment['id']}/maintenance", json={**LOG, "performed_by": "Acme Services"})).json()
    assert body["performed_by"] == "Acme Services" and body["performed_by_id"] == str(users["technician"].id)


async def test_date_only_input_is_utc_midnight(technician, equipment):
    body = (await technician.post(f"/equipment/{equipment['id']}/maintenance", json={**LOG, "performed_at": "2026-11-16"})).json()
    assert body["performed_at"] == "2026-11-16T00:00:00Z"


async def test_invalid_duration_is_422(technician, equipment):
    assert (await technician.post(f"/equipment/{equipment['id']}/maintenance", json={**LOG, "duration_minutes": 0})).status_code == 422


async def test_unknown_equipment_is_404(technician, users):
    assert (await technician.post(f"/equipment/{ZERO}/maintenance", json=LOG)).status_code == 404


async def test_history_is_newest_first(technician, equipment):
    for day in ("2026-01-01", "2026-03-01", "2026-02-01"):
        await technician.post(f"/equipment/{equipment['id']}/maintenance", json={**LOG, "performed_at": day})
    dates = [log["performed_at"][:10] for log in (await technician.get(f"/equipment/{equipment['id']}/maintenance")).json()]
    assert dates == ["2026-03-01", "2026-02-01", "2026-01-01"]


async def test_empty_history_is_200(technician, equipment):
    assert (await technician.get(f"/equipment/{equipment['id']}/maintenance")).json() == []


async def test_upcoming_window_includes_today_through_day_30(technician, make_equipment):
    today = utc_now().date()                         # the API defines "today" in UTC, not the laptop's timezone
    for offset in (-1, 0, 30, 31):                  # one machine per planned date
        machine = await make_equipment()
        await technician.post(f"/equipment/{machine['id']}/maintenance",
                              json={**LOG, "description": f"d{offset}", "next_scheduled_at": str(today + timedelta(days=offset))})
    got = [log["description"] for log in (await technician.get("/maintenance/upcoming")).json()]
    assert got == ["d0", "d30"]


async def test_upcoming_uses_only_each_machines_latest_plan(technician, admin, make_equipment):
    machine, retired = await make_equipment(), await make_equipment()
    soon = str(date.today() + timedelta(days=5))
    # An old service planned a visit soon, but a newer service moved the plan out to 90 days: not upcoming.
    await technician.post(f"/equipment/{machine['id']}/maintenance", json={**LOG, "performed_at": "2026-01-01", "next_scheduled_at": soon})
    await technician.post(f"/equipment/{machine['id']}/maintenance",
                          json={**LOG, "performed_at": str(date.today()), "next_scheduled_at": str(date.today() + timedelta(days=90))})
    # Retired machines are never "due".
    await technician.post(f"/equipment/{retired['id']}/maintenance", json={**LOG, "next_scheduled_at": soon})
    await admin.delete(f"/equipment/{retired['id']}")
    assert (await technician.get("/maintenance/upcoming")).json() == []


async def test_get_log_and_404(technician, equipment):
    log = (await technician.post(f"/equipment/{equipment['id']}/maintenance", json=LOG)).json()
    assert (await technician.get(f"/maintenance/{log['id']}")).json()["created_at"] == log["created_at"]
    assert (await technician.get(f"/maintenance/{ZERO}")).status_code == 404


async def test_overdue_lists_machines_past_their_latest_plan(technician, admin, make_equipment):
    late, fine, retired = [await make_equipment() for _ in range(3)]
    past, future = str(date.today() - timedelta(days=5)), str(date.today() + timedelta(days=5))
    await technician.post(f"/equipment/{late['id']}/maintenance", json={**LOG, "performed_at": "2026-01-01", "next_scheduled_at": past})
    # An old overdue plan superseded by a newer service with a future plan is not overdue.
    await technician.post(f"/equipment/{fine['id']}/maintenance", json={**LOG, "performed_at": "2026-01-01", "next_scheduled_at": past})
    await technician.post(f"/equipment/{fine['id']}/maintenance", json={**LOG, "performed_at": str(date.today()), "next_scheduled_at": future})
    await technician.post(f"/equipment/{retired['id']}/maintenance", json={**LOG, "next_scheduled_at": past})
    await admin.delete(f"/equipment/{retired['id']}")
    assert [m["equipment_id"] for m in (await technician.get("/maintenance/overdue")).json()] == [late["id"]]
