from __future__ import annotations

import asyncio
import os
from datetime import datetime
from html import escape
from typing import Annotated

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field


class MesSettings(BaseModel):
    username: str = os.getenv("MES_DEMO_USERNAME", "mes-demo")
    password: str = os.getenv("MES_DEMO_PASSWORD", "mes-password")
    internal_token: str = os.getenv("INTERNAL_SERVICE_TOKEN", "change-me-in-local-env")
    initial_failure_mode: str = os.getenv("MES_FAILURE_MODE", "normal")
    api_delay_seconds: float = float(os.getenv("MES_API_DELAY_SECONDS", "15"))


class WorkOrderPayload(BaseModel):
    incident_no: str = Field(min_length=1, max_length=80)
    equipment_code: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    priority: str = Field(min_length=1, max_length=10)
    description: str = Field(min_length=1, max_length=4000)
    assigned_team: str = Field(min_length=1, max_length=120)


class FailureMode(BaseModel):
    mode: str = Field(pattern="^(normal|unavailable|timeout|validation_error)$")


settings = MesSettings()
app = FastAPI(title="Legacy MES Demo", version="0.1.0")
_failure_mode = settings.initial_failure_mode
_work_orders: list[dict[str, str]] = []


def reset_state() -> None:
    global _failure_mode
    _failure_mode = settings.initial_failure_mode
    _work_orders.clear()


def next_external_id() -> str:
    return f"MES-WO-{datetime.utcnow():%Y%m%d}-{len(_work_orders) + 1:04d}"


def require_internal_token(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    if x_internal_token != settings.internal_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_internal_token")


def is_authenticated(request: Request) -> bool:
    return request.cookies.get("mes_session") == "demo-session"


def require_session(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login_required")


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{escape(title)}</title></head>
<body>
<header><h1 data-testid="page-title">{escape(title)}</h1><nav><a href="/work-orders">Work orders</a> | <a href="/work-orders/new">New work order</a></nav></header>
<main>{body}</main>
</body>
</html>"""
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/login", response_class=HTMLResponse)
async def login_page() -> HTMLResponse:
    return page(
        "Legacy MES Login",
        """<form method="post" action="/login" data-testid="login-form">
  <label>Username <input name="username" data-testid="username-input" autocomplete="username"></label>
  <label>Password <input name="password" type="password" data-testid="password-input" autocomplete="current-password"></label>
  <button type="submit" data-testid="login-submit">Sign in</button>
</form>""",
    )


@app.post("/login")
async def login(username: Annotated[str, Form()], password: Annotated[str, Form()]) -> Response:
    if username != settings.username or password != settings.password:
        return page("Legacy MES Login", '<p data-testid="login-error">Invalid username or password</p>')
    response = RedirectResponse("/work-orders", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie("mes_session", "demo-session", httponly=True, samesite="lax")
    return response


@app.get("/work-orders", response_class=HTMLResponse)
async def work_order_list(request: Request, _: None = Depends(require_session)) -> HTMLResponse:
    rows = "".join(
        f'<tr><td><a data-testid="work-order-link" href="/work-orders/{escape(item["external_id"])}">{escape(item["external_id"])}</a></td><td>{escape(item["title"])}</td><td>{escape(item["priority"])}</td></tr>'
        for item in _work_orders
    )
    return page("Legacy MES Work Orders", f'<table data-testid="work-order-table"><tbody>{rows}</tbody></table>')


@app.get("/work-orders/new", response_class=HTMLResponse)
async def new_work_order_page(request: Request, _: None = Depends(require_session)) -> HTMLResponse:
    return page(
        "New Work Order",
        """<form method="post" action="/work-orders/new" data-testid="new-work-order-form">
  <label>Incident No <input name="incident_no" data-testid="incident-no-input"></label>
  <label>Equipment Code <input name="equipment_code" data-testid="equipment-code-input"></label>
  <label>Title <input name="title" data-testid="title-input"></label>
  <label>Priority <select name="priority" data-testid="priority-select"><option>P1</option><option>P2</option><option>P3</option><option>P4</option></select></label>
  <label>Description <textarea name="description" data-testid="description-input"></textarea></label>
  <label>Assigned Team <input name="assigned_team" data-testid="assigned-team-input"></label>
  <button type="submit" data-testid="submit-work-order">Create</button>
</form>""",
    )


@app.post("/work-orders/new")
async def create_work_order_form(
    request: Request,
    incident_no: Annotated[str, Form()],
    equipment_code: Annotated[str, Form()],
    title: Annotated[str, Form()],
    priority: Annotated[str, Form()],
    description: Annotated[str, Form()],
    assigned_team: Annotated[str, Form()],
    _: None = Depends(require_session),
) -> Response:
    payload = WorkOrderPayload(
        incident_no=incident_no,
        equipment_code=equipment_code,
        title=title,
        priority=priority,
        description=description,
        assigned_team=assigned_team,
    )
    external_id = save_work_order(payload)
    return RedirectResponse(f"/work-orders/{external_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/work-orders/{external_id}", response_class=HTMLResponse)
async def work_order_detail(external_id: str, _: None = Depends(require_session)) -> HTMLResponse:
    item = next((row for row in _work_orders if row["external_id"] == external_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="work_order_not_found")
    return page(
        f"Work Order {external_id}",
        f"""<dl data-testid="work-order-detail">
  <dt>External ID</dt><dd data-testid="external-id">{escape(item["external_id"])}</dd>
  <dt>Incident</dt><dd>{escape(item["incident_no"])}</dd>
  <dt>Equipment</dt><dd>{escape(item["equipment_code"])}</dd>
  <dt>Title</dt><dd>{escape(item["title"])}</dd>
</dl>""",
    )


def save_work_order(payload: WorkOrderPayload) -> str:
    external_id = next_external_id()
    _work_orders.append({"external_id": external_id, **payload.model_dump()})
    return external_id


@app.post("/api/work-orders", status_code=status.HTTP_201_CREATED)
async def create_work_order_api(payload: WorkOrderPayload) -> dict[str, object]:
    if _failure_mode == "unavailable":
        raise HTTPException(status_code=503, detail="legacy_mes_unavailable")
    if _failure_mode == "timeout":
        await asyncio.sleep(settings.api_delay_seconds)
    if _failure_mode == "validation_error":
        raise HTTPException(status_code=422, detail="legacy_mes_business_validation_error")
    external_id = save_work_order(payload)
    return {"success": True, "external_id": external_id}


@app.post("/internal/failure-mode")
async def set_failure_mode(payload: FailureMode, _: None = Depends(require_internal_token)) -> dict[str, str]:
    global _failure_mode
    _failure_mode = payload.mode
    return {"mode": _failure_mode}
