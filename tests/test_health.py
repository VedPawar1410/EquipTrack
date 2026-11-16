async def test_health_reports_database_ok(anon):
    response = await anon.get("http://test/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_root_points_to_docs(anon):
    assert (await anon.get("http://test/")).json()["docs"] == "/docs"


async def test_health_is_503_when_database_is_down(anon):
    from app.core.database import get_db
    from app.main import app

    class BrokenSession:
        async def execute(self, *_):
            raise ConnectionError("db down")

    async def broken_db():
        yield BrokenSession()

    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = broken_db
    try:
        response = await anon.get("http://test/health")
    finally:
        app.dependency_overrides[get_db] = previous
    assert response.status_code == 503
