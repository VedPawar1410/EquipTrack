from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.schemas.common import utc_now
from tests.conftest import PASSWORD


async def login(client, username, password=PASSWORD):
    return await client.post("/auth/login", data={"username": username, "password": password})


# ---------- login

async def test_login_returns_bearer_token(anon, users):
    response = await login(anon, "tech")
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    me = await anon.get("/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.json()["username"] == "tech"


async def test_login_accepts_email(anon, users):
    assert (await login(anon, "tech@plant.test")).status_code == 200


@pytest.mark.parametrize("username, password", [("tech", "wrong-password"), ("nobody", PASSWORD), ("gone", PASSWORD)])
async def test_login_failures_are_indistinguishable(anon, users, username, password):
    response = await login(anon, username, password)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


# ---------- token validation

async def test_no_token_is_401(anon):
    assert (await anon.get("/equipment")).status_code == 401


async def test_garbage_token_is_401(anon):
    assert (await anon.get("/equipment", headers={"Authorization": "Bearer not.a.jwt"})).status_code == 401


async def test_expired_token_is_401(anon, users):
    token = jwt.encode({"sub": str(users["technician"].id),
                        "exp": utc_now() - timedelta(minutes=1)}, settings.jwt_secret_key, algorithm="HS256")
    assert (await anon.get("/equipment", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_token_signed_with_another_key_is_401(anon, users):
    forged = jwt.encode({"sub": str(users["admin"].id)}, "attacker-key-that-is-at-least-32-chars!", algorithm="HS256")
    assert (await anon.get("/equipment", headers={"Authorization": f"Bearer {forged}"})).status_code == 401


async def test_me_never_exposes_password_hash(technician):
    body = (await technician.get("/auth/me")).json()
    assert body["role"] == "technician" and "hashed_password" not in body


# ---------- account management (admin only)

NEW_USER = {"username": "rkumar", "email": "ravi@plant.test", "password": "Temp-Pass-123", "role": "technician"}


async def test_admin_creates_user(admin):
    response = await admin.post("/auth/users", json=NEW_USER)
    assert response.status_code == 201
    assert response.json()["is_active"] is True and "hashed_password" not in response.json()


async def test_role_defaults_to_technician(admin):
    body = {k: v for k, v in NEW_USER.items() if k != "role"}
    assert (await admin.post("/auth/users", json=body)).json()["role"] == "technician"


async def test_duplicate_username_is_409(admin):
    await admin.post("/auth/users", json=NEW_USER)
    assert (await admin.post("/auth/users", json={**NEW_USER, "email": "other@plant.test"})).status_code == 409


@pytest.mark.parametrize("field, value", [("password", "short"), ("role", "boss"), ("email", "not-an-email"),
                                          ("username", "a"), ("username", "has spaces")])
async def test_invalid_user_input_is_422(admin, field, value):
    assert (await admin.post("/auth/users", json={**NEW_USER, field: value})).status_code == 422


@pytest.mark.parametrize("role_fixture", ["technician", "supervisor"])
async def test_only_admin_manages_users(clients, role_fixture):
    client = clients[role_fixture]
    assert (await client.post("/auth/users", json=NEW_USER)).status_code == 403
    assert (await client.get("/auth/users")).status_code == 403


async def test_admin_cannot_demote_or_deactivate_self(admin, users):
    admin_id = users["admin"].id
    assert (await admin.patch(f"/auth/users/{admin_id}/role", json={"role": "technician"})).status_code == 422
    assert (await admin.patch(f"/auth/users/{admin_id}/deactivate")).status_code == 422


async def test_role_change_applies_to_existing_token(admin, supervisor, users, equipment):
    assert (await supervisor.patch(f"/equipment/{equipment['id']}/status", json={"status": "active"})).status_code == 200
    await admin.patch(f"/auth/users/{users['supervisor'].id}/role", json={"role": "technician"})
    assert (await supervisor.patch(f"/equipment/{equipment['id']}/status", json={"status": "active"})).status_code == 403


async def test_deactivation_revokes_token_and_login(admin, technician, anon, users):
    assert (await admin.patch(f"/auth/users/{users['technician'].id}/deactivate")).json()["is_active"] is False
    assert (await technician.get("/equipment")).status_code == 401
    assert (await login(anon, "tech")).status_code == 401
    await admin.patch(f"/auth/users/{users['technician'].id}/activate")
    assert (await technician.get("/equipment")).status_code == 200


async def test_unknown_user_id_is_404(admin):
    assert (await admin.patch("/auth/users/00000000-0000-0000-0000-000000000000/deactivate")).status_code == 404


async def test_change_own_password(technician, anon):
    wrong = await technician.post("/auth/me/password", json={"current_password": "nope", "new_password": "New-Pass-456"})
    assert wrong.status_code == 400
    ok = await technician.post("/auth/me/password", json={"current_password": PASSWORD, "new_password": "New-Pass-456"})
    assert ok.status_code == 204
    assert (await login(anon, "tech")).status_code == 401
    assert (await login(anon, "tech", "New-Pass-456")).status_code == 200


async def test_admin_lists_users(admin):
    assert [u["username"] for u in (await admin.get("/auth/users")).json()] == ["admin", "gone", "sup", "tech"]
