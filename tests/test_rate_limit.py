"""Deployment hardening: the per-user AI limit, and accepting a hosted database's connection URL."""
import pytest

from app.core.config import settings, to_asyncpg_url
from app.core.rate_limit import SlidingWindowLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_sliding_window_frees_a_slot_once_the_oldest_request_ages_out():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(window_seconds=60, clock=clock)
    assert limiter.hit("ravi", 2) is None
    clock.now += 10
    assert limiter.hit("ravi", 2) is None
    assert limiter.hit("ravi", 2) == 50          # the first request leaves the window in 50 s
    assert limiter.hit("maria", 2) is None       # limits are per key
    clock.now += 50
    assert limiter.hit("ravi", 2) is None        # the first request has aged out
    assert limiter.hit("ravi", 2) == 10


async def test_ai_requests_are_limited_per_user(technician, supervisor, make_equipment, monkeypatch):
    monkeypatch.setattr(settings, "ai_requests_per_hour", 2)
    machine = await make_equipment()
    assert (await technician.post("/ai/ask", json={"question": "What does E-47 mean?"})).status_code == 200
    # /ai/diagnose shares the same budget: both may spend LLM quota
    diagnose = await technician.post(f"/ai/diagnose/{machine['id']}", json={"symptom": "Spindle vibrates"})
    assert diagnose.status_code == 200

    blocked = await technician.post("/ai/ask", json={"question": "What does E-47 mean?"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "AI limit reached (2 questions per hour). Try again in 60 min."
    assert 3590 <= int(blocked.headers["Retry-After"]) <= 3600

    assert (await supervisor.post("/ai/ask", json={"question": "What does E-47 mean?"})).status_code == 200


async def test_the_limit_never_counts_anonymous_requests(anon):
    assert (await anon.post("/ai/ask", json={"question": "What does E-47 mean?"})).status_code == 401


@pytest.mark.parametrize(("given", "expected"), [
    # Neon's copy-paste URL: plain scheme, libpq's sslmode, and channel_binding (unknown to asyncpg)
    ("postgresql://u:p%40ss@ep-x.neon.tech/db?sslmode=require&channel_binding=require",
     "postgresql+asyncpg://u:p%40ss@ep-x.neon.tech/db?ssl=require"),
    ("postgres://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
    # Already correct (local docker compose): unchanged
    ("postgresql+asyncpg://equiptrack:devpassword@postgres:5432/equiptrack",
     "postgresql+asyncpg://equiptrack:devpassword@postgres:5432/equiptrack"),
])
def test_hosted_database_urls_are_made_asyncpg_compatible(given, expected):
    assert to_asyncpg_url(given) == expected
