import pytest

from tests.conftest import EQUIPMENT

ZERO = "00000000-0000-0000-0000-000000000000"


async def test_create_sets_server_fields(admin):
    response = await admin.post("/equipment", json=EQUIPMENT)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active" and body["id"] and body["created_at"].endswith("Z")


async def test_purchase_dates_are_optional(make_equipment):
    body = await make_equipment(purchased_at=None, warranty_expires_at=None)
    assert body["purchased_at"] is None


@pytest.mark.parametrize("bad", [
    {"name": "x"},                                       # missing required fields
    {**EQUIPMENT, "equipment_type": "Toaster"},          # not an EquipmentType
    {**EQUIPMENT, "name": "x" * 101},                    # longer than VARCHAR(100): 422, not a DB error
])
async def test_invalid_equipment_is_422(admin, bad):
    assert (await admin.post("/equipment", json=bad)).status_code == 422


async def test_duplicate_serial_is_409(admin, equipment):
    response = await admin.post("/equipment", json={**EQUIPMENT, "serial_number": equipment["serial_number"]})
    assert response.status_code == 409


async def test_update_to_taken_serial_is_409(admin, make_equipment):
    first, second = await make_equipment(), await make_equipment()
    response = await admin.put(f"/equipment/{second['id']}", json={**EQUIPMENT, "serial_number": first["serial_number"]})
    assert response.status_code == 409


async def test_get_unknown_is_404(technician):
    assert (await technician.get(f"/equipment/{ZERO}")).status_code == 404


async def test_empty_list_is_200(technician):
    response = await technician.get("/equipment")
    assert response.status_code == 200 and response.json() == []


async def test_filters_and_case_insensitive_search(technician, make_equipment):
    await make_equipment(name="CNC Lathe A3", department="Machining")
    await make_equipment(name="Paint Robot 2", equipment_type="Paint Robot", department="Paint Shop")
    assert [e["name"] for e in (await technician.get("/equipment?search=lathe")).json()] == ["CNC Lathe A3"]
    assert len((await technician.get("/equipment?department=Paint Shop")).json()) == 1
    assert len((await technician.get("/equipment?type=Paint Robot")).json()) == 1
    assert (await technician.get("/equipment?department=Nowhere")).json() == []


async def test_pagination(technician, make_equipment):
    for _ in range(3):
        await make_equipment()
    page = (await technician.get("/equipment?limit=2&offset=0")).json()
    rest = (await technician.get("/equipment?limit=2&offset=2")).json()
    assert len(page) == 2 and len(rest) == 1
    assert (await technician.get("/equipment?limit=0")).status_code == 422


async def test_put_updates_fields_and_updated_at(admin, equipment):
    response = await admin.put(f"/equipment/{equipment['id']}", json={**EQUIPMENT, "serial_number": equipment["serial_number"], "name": "Renamed"})
    assert response.json()["name"] == "Renamed"
    assert response.json()["updated_at"] > equipment["updated_at"]


async def test_status_change(supervisor, equipment):
    response = await supervisor.patch(f"/equipment/{equipment['id']}/status", json={"status": "under maintenance"})
    assert response.json()["status"] == "under maintenance"
    assert (await supervisor.patch(f"/equipment/{equipment['id']}/status", json={"status": "broken"})).status_code == 422


async def test_soft_delete_retires(admin, equipment):
    assert (await admin.delete(f"/equipment/{equipment['id']}")).status_code == 204
    assert (await admin.get(f"/equipment/{equipment['id']}")).json()["status"] == "retired"


async def test_hard_delete_cascades_to_children(admin, technician, supervisor, equipment):
    eid = equipment["id"]
    log = (await technician.post(f"/equipment/{eid}/maintenance", json={"log_type": "Inspection", "performed_at": "2026-11-01", "description": "ok"})).json()
    issue = (await technician.post("/issues", json={"equipment_id": eid, "title": "Noise", "severity": "Low"})).json()
    part = (await supervisor.post(f"/equipment/{eid}/parts", json={"part_name": "Belt"})).json()
    assert (await admin.delete(f"/equipment/{eid}/hard")).status_code == 204
    assert (await admin.get(f"/maintenance/{log['id']}")).status_code == 404
    assert (await admin.get(f"/issues/{issue['id']}")).status_code == 404
    assert (await admin.get(f"/parts/{part['id']}")).status_code == 404


# ---------- role matrix: who may do what

@pytest.mark.parametrize("role, expected", [("technician", 403), ("supervisor", 403), ("admin", 201)])
async def test_create_requires_admin(clients, role, expected):
    client = clients[role]
    assert (await client.post("/equipment", json=EQUIPMENT)).status_code == expected


@pytest.mark.parametrize("role, expected", [("technician", 403), ("supervisor", 200)])
async def test_status_change_requires_supervisor(clients, equipment, role, expected):
    client = clients[role]
    assert (await client.patch(f"/equipment/{equipment['id']}/status", json={"status": "active"})).status_code == expected


@pytest.mark.parametrize("method, path", [("put", ""), ("delete", ""), ("delete", "/hard")])
async def test_supervisor_cannot_change_master_data(supervisor, equipment, method, path):
    kwargs = {"json": EQUIPMENT} if method == "put" else {}
    assert (await getattr(supervisor, method)(f"/equipment/{equipment['id']}{path}", **kwargs)).status_code == 403


async def test_role_is_checked_before_existence(technician):
    # A technician learns nothing about which ids exist: 403, not 404.
    assert (await technician.put(f"/equipment/{ZERO}", json=EQUIPMENT)).status_code == 403


async def test_filter_by_status_and_summary(technician, supervisor, make_equipment):
    a, _ = await make_equipment(), await make_equipment()
    await supervisor.patch(f"/equipment/{a['id']}/status", json={"status": "under maintenance"})
    assert [e["id"] for e in (await technician.get("/equipment?status=under maintenance")).json()] == [a["id"]]
    assert (await technician.get(f"/equipment/{a['id']}/summary")).json()["id"] == a["id"]
