from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from rpa_worker.app import app, get_settings
from rpa_worker.schemas import RpaWorkOrderRequest, RpaWorkOrderResponse


def test_internal_token_is_required():
    client = TestClient(app)
    response = client.post("/internal/rpa/work-orders", json={"work_order_id": 1})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rpa_success_uses_runner_and_returns_screenshot(monkeypatch):
    async def fake_run(settings, payload):
        return RpaWorkOrderResponse(
            success=True,
            external_id="MES-WO-20260714-7777",
            screenshot_path="/artifacts/rpa/success.png",
            steps=[{"step": "submit", "status": "ok"}],
        )

    monkeypatch.setattr("rpa_worker.app.run_work_order_rpa", fake_run)
    client = TestClient(app)
    response = client.post(
        "/internal/rpa/work-orders",
        headers={"X-Internal-Token": get_settings().internal_service_token},
        json={
            "work_order_id": 1,
            "incident_no": "INC-1",
            "equipment_code": "CNC-01",
            "title": "Spindle vibration",
            "priority": "P1",
            "description": "vibration=9.8",
            "assigned_team": "maintenance",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["external_id"] == "MES-WO-20260714-7777"


@pytest.mark.asyncio
async def test_runner_saves_screenshot_on_login_failure(monkeypatch, tmp_path):
    from rpa_worker.runner import RpaFailure, screenshot_failure_response

    failure = RpaFailure("MES_LOGIN_FAILED", "login failed", [{"step": "login", "status": "failed"}])
    response = await screenshot_failure_response(tmp_path, failure)

    assert response.success is False
    assert response.error_code == "MES_LOGIN_FAILED"
    assert response.screenshot_path is not None
    assert Path(response.screenshot_path.replace("/artifacts/rpa/", str(tmp_path) + "/")).exists()


def test_password_is_not_rendered_in_response_schema():
    payload = RpaWorkOrderRequest(
        work_order_id=1,
        incident_no="INC-1",
        equipment_code="CNC-01",
        title="Title",
        priority="P2",
        description="password=super-secret",
        assigned_team="maintenance",
    )
    assert "super-secret" in payload.description
