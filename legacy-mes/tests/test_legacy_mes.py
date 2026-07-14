from httpx import ASGITransport, AsyncClient
import pytest

from legacy_mes.app import app, reset_state


@pytest.fixture(autouse=True)
def clean_state():
    reset_state()


@pytest.mark.asyncio
async def test_mes_api_creates_work_order_in_normal_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/work-orders",
            json={
                "incident_no": "INC-1",
                "equipment_code": "CNC-01",
                "title": "Spindle vibration",
                "priority": "P1",
                "description": "vibration=9.8",
                "assigned_team": "maintenance",
            },
        )

    assert response.status_code == 201
    assert response.json()["external_id"].startswith("MES-WO-")


@pytest.mark.asyncio
async def test_mes_api_returns_business_validation_error_without_rpa_fallback_class():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/work-orders",
            json={
                "incident_no": "INC-1",
                "equipment_code": "",
                "title": "Missing equipment",
                "priority": "P2",
                "description": "bad input",
                "assigned_team": "maintenance",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_mes_api_can_return_503_via_protected_failure_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        mode = await client.post("/internal/failure-mode", headers={"X-Internal-Token": "change-me-in-local-env"}, json={"mode": "unavailable"})
        response = await client.post(
            "/api/work-orders",
            json={
                "incident_no": "INC-1",
                "equipment_code": "CNC-01",
                "title": "Spindle vibration",
                "priority": "P1",
                "description": "vibration=9.8",
                "assigned_team": "maintenance",
            },
        )

    assert mode.status_code == 200
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_mes_login_page_uses_stable_form_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/login")

    assert response.status_code == 200
    assert 'data-testid="username-input"' in response.text
    assert 'data-testid="password-input"' in response.text
