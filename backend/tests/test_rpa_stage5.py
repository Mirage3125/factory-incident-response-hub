import pytest
from httpx import Request, Response
from sqlalchemy import select

from factory_hub.domain.enums import RpaStatus, WorkOrderCreationMethod
from factory_hub.domain.models import RpaRun, WorkOrder


@pytest.mark.asyncio
async def test_backend_rpa_endpoint_updates_work_order_from_worker_success(api_client, db_session, monkeypatch):
    work_order = (await db_session.execute(select(WorkOrder).order_by(WorkOrder.id))).scalars().first()

    class FakeRpaClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            assert url == "http://rpa-worker:8200/internal/rpa/work-orders"
            assert kwargs["headers"]["X-Internal-Token"] == "change-me-in-local-env"
            assert kwargs["json"]["work_order_id"] == work_order.id
            assert "title" in kwargs["json"]
            return Response(
            200,
            request=Request("POST", url),
            json={
                "success": True,
                "external_id": "MES-WO-20260714-9001",
                "screenshot_path": "/artifacts/rpa/success.png",
                "steps": [{"step": "submit", "status": "ok"}],
                "error_code": None,
                "error_message": None,
            },
        )

    monkeypatch.setattr("factory_hub.services.workflow.httpx.AsyncClient", FakeRpaClient)

    response = await api_client.post(
        "/api/internal/rpa/work-orders",
        headers={"X-Internal-Token": "change-me-in-local-env"},
        json={"work_order_id": work_order.id, "reason": "MES API 503"},
    )

    assert response.status_code == 200
    assert response.json()["external_id"] == "MES-WO-20260714-9001"

    await db_session.refresh(work_order)
    assert work_order.creation_method == WorkOrderCreationMethod.RPA.value
    assert work_order.external_id == "MES-WO-20260714-9001"

    run = (await db_session.execute(select(RpaRun).order_by(RpaRun.id.desc()).limit(1))).scalar_one()
    assert run.status == RpaStatus.SUCCEEDED.value
    assert run.external_id == "MES-WO-20260714-9001"
    assert run.screenshot_path == "/artifacts/rpa/success.png"


@pytest.mark.asyncio
async def test_backend_rpa_endpoint_records_worker_failure_without_fake_external_id(api_client, db_session, monkeypatch):
    work_order = (await db_session.execute(select(WorkOrder).order_by(WorkOrder.id))).scalars().first()

    class FakeRpaClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            return Response(
                200,
                request=Request("POST", url),
                json={
                    "success": False,
                    "external_id": None,
                    "screenshot_path": "/artifacts/rpa/failure.png",
                    "steps": [{"step": "login", "status": "failed"}],
                    "error_code": "MES_LOGIN_FAILED",
                    "error_message": "login failed",
                },
            )

    monkeypatch.setattr("factory_hub.services.workflow.httpx.AsyncClient", FakeRpaClient)

    response = await api_client.post(
        "/api/internal/rpa/work-orders",
        headers={"X-Internal-Token": "change-me-in-local-env"},
        json={"work_order_id": work_order.id, "reason": "MES API 503"},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == "MES_LOGIN_FAILED"

    await db_session.refresh(work_order)
    assert work_order.external_id is None

    run = (await db_session.execute(select(RpaRun).order_by(RpaRun.id.desc()).limit(1))).scalar_one()
    assert run.status == RpaStatus.FAILED.value
    assert run.external_id is None
    assert run.screenshot_path == "/artifacts/rpa/failure.png"


@pytest.mark.asyncio
async def test_backend_rpa_endpoint_sanitizes_worker_errors(api_client, db_session, monkeypatch):
    work_order = (await db_session.execute(select(WorkOrder).order_by(WorkOrder.id))).scalars().first()

    class FakeRpaClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            return Response(
                200,
                request=Request("POST", url),
                json={
                    "success": False,
                    "external_id": None,
                    "screenshot_path": "/artifacts/rpa/failure.png",
                    "steps": [],
                    "error_code": "RPA_FAILED",
                    "error_message": "password=super-secret token=private-token",
                },
            )

    monkeypatch.setattr("factory_hub.services.workflow.httpx.AsyncClient", FakeRpaClient)

    response = await api_client.post(
        "/api/internal/rpa/work-orders",
        headers={"X-Internal-Token": "change-me-in-local-env"},
        json={"work_order_id": work_order.id, "reason": "MES API 503"},
    )

    assert response.status_code == 502
    assert "super-secret" not in response.text
    assert "private-token" not in response.text

    run = (await db_session.execute(select(RpaRun).order_by(RpaRun.id.desc()).limit(1))).scalar_one()
    assert "super-secret" not in run.error_message
    assert "private-token" not in run.error_message
    assert "[REDACTED]" in run.error_message
