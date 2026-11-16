from datetime import date, timedelta

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


async def test_upcoming_window_includes_today_through_day_30(technician, equipment):
    today = date.today()
    for offset in (-1, 0, 30, 31):
        await technician.post(f"/equipment/{equipment['id']}/maintenance",
                              json={**LOG, "description": f"d{offset}", "next_scheduled_at": str(today + timedelta(days=offset))})
    got = [log["description"] for log in (await technician.get("/maintenance/upcoming")).json()]
    assert got == ["d0", "d30"]


async def test_get_log_and_404(technician, equipment):
    log = (await technician.post(f"/equipment/{equipment['id']}/maintenance", json=LOG)).json()
    assert (await technician.get(f"/maintenance/{log['id']}")).json()["created_at"] == log["created_at"]
    assert (await technician.get(f"/maintenance/{ZERO}")).status_code == 404
