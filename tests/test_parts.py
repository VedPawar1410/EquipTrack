import asyncio

import pytest

ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
async def part(supervisor, equipment):
    response = await supervisor.post(f"/equipment/{equipment['id']}/parts",
                                     json={"part_name": "Belt drive", "quantity_in_stock": 5, "reorder_threshold": 2})
    assert response.status_code == 201
    return response.json()


async def change(client, part_id, delta):
    return await client.patch(f"/parts/{part_id}/quantity", json={"quantity_change": delta})


async def test_zero_stock_is_allowed(supervisor, equipment):
    response = await supervisor.post(f"/equipment/{equipment['id']}/parts", json={"part_name": "Die", "quantity_in_stock": 0})
    assert response.status_code == 201


async def test_technician_cannot_add_parts(technician, equipment):
    assert (await technician.post(f"/equipment/{equipment['id']}/parts", json={"part_name": "x"})).status_code == 403


async def test_consume_and_restock_rules(technician, supervisor, part):
    assert (await change(technician, part["id"], -4)).json()["quantity_in_stock"] == 1
    assert (await change(technician, part["id"], -2)).status_code == 422    # would go below zero
    assert (await change(technician, part["id"], 3)).status_code == 403     # restocking is supervisor-level
    assert (await change(supervisor, part["id"], 3)).json()["quantity_in_stock"] == 4
    assert (await change(supervisor, part["id"], 0)).status_code == 422


async def test_unknown_part_is_404(supervisor, users):
    assert (await change(supervisor, ZERO, 1)).status_code == 404
    assert (await supervisor.get(f"/parts/{ZERO}")).status_code == 404


async def test_low_stock(technician, supervisor, equipment, part):
    assert (await technician.get("/parts/low-stock")).json() == []
    await change(technician, part["id"], -3)                                  # 2 left == threshold
    assert [p["id"] for p in (await technician.get("/parts/low-stock")).json()] == [part["id"]]


async def test_parts_list_empty_is_200(technician, equipment):
    assert (await technician.get(f"/equipment/{equipment['id']}/parts")).json() == []


async def test_concurrent_consumption_never_oversells(technician, part):
    """20 technicians grab the last 5 belts at the same moment: exactly 5 succeed."""
    responses = await asyncio.gather(*(change(technician, part["id"], -1) for _ in range(20)))
    codes = [r.status_code for r in responses]
    assert codes.count(200) == 5 and codes.count(422) == 15
    assert (await technician.get(f"/parts/{part['id']}")).json()["quantity_in_stock"] == 0
