import pytest
from httpx import ASGITransport, AsyncClient

from factory_hub.database import get_database
from factory_hub.main import create_app


@pytest.mark.asyncio
async def test_health_returns_alive_status():
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_returns_ready_when_database_ping_succeeds():
    app = create_app()

    class ReadyDatabase:
        async def ping(self) -> None:
            return None

    app.dependency_overrides[get_database] = lambda: ReadyDatabase()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_ready_returns_503_when_database_ping_fails():
    app = create_app()

    class FailingDatabase:
        async def ping(self) -> None:
            raise RuntimeError("database unavailable")

    app.dependency_overrides[get_database] = lambda: FailingDatabase()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database_unavailable"}
