from __future__ import annotations

import time
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from rpa_worker.schemas import RpaWorkOrderRequest, RpaWorkOrderResponse


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00"
    b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


class RpaFailure(Exception):
    def __init__(self, code: str, message: str, steps: list[dict[str, str]]) -> None:
        super().__init__(message)
        self.code = code
        self.steps = steps


def artifact_path(root: Path, prefix: str, work_order_id: int | None = None) -> Path:
    stamp = int(time.time() * 1000)
    suffix = f"-{work_order_id}" if work_order_id is not None else ""
    return root / f"{prefix}{suffix}-{stamp}.png"


def public_artifact_path(path: Path) -> str:
    return f"/artifacts/rpa/{path.name}"


async def screenshot_failure_response(root: Path, failure: RpaFailure, work_order_id: int | None = None) -> RpaWorkOrderResponse:
    root.mkdir(parents=True, exist_ok=True)
    path = artifact_path(root, "failure", work_order_id)
    path.write_bytes(PNG_1X1)
    return RpaWorkOrderResponse(
        success=False,
        external_id=None,
        screenshot_path=public_artifact_path(path),
        steps=failure.steps,
        error_code=failure.code,
        error_message=failure.args[0],
    )


async def run_work_order_rpa(settings, payload: RpaWorkOrderRequest) -> RpaWorkOrderResponse:
    steps: list[dict[str, str]] = []
    root = Path(settings.rpa_artifact_root)
    root.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=settings.rpa_headless)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            steps.append({"step": "open_login", "status": "started"})
            await page.goto(f"{settings.legacy_mes_url.rstrip('/')}/login", wait_until="networkidle", timeout=settings.rpa_timeout_ms)
            steps[-1]["status"] = "ok"

            steps.append({"step": "login", "status": "started"})
            await page.get_by_test_id("username-input").fill(settings.mes_username)
            await page.get_by_test_id("password-input").fill(settings.mes_password)
            await page.get_by_test_id("login-submit").click()
            await page.wait_for_url("**/work-orders", timeout=settings.rpa_timeout_ms)
            steps[-1]["status"] = "ok"

            steps.append({"step": "open_new_work_order", "status": "started"})
            await page.goto(f"{settings.legacy_mes_url.rstrip('/')}/work-orders/new", wait_until="networkidle", timeout=settings.rpa_timeout_ms)
            steps[-1]["status"] = "ok"

            steps.append({"step": "fill_form", "status": "started"})
            await page.get_by_test_id("incident-no-input").fill(payload.incident_no)
            await page.get_by_test_id("equipment-code-input").fill(payload.equipment_code)
            await page.get_by_test_id("title-input").fill(payload.title)
            await page.get_by_test_id("priority-select").select_option(payload.priority)
            await page.get_by_test_id("description-input").fill(payload.description)
            await page.get_by_test_id("assigned-team-input").fill(payload.assigned_team)
            steps[-1]["status"] = "ok"

            steps.append({"step": "submit", "status": "started"})
            await page.get_by_test_id("submit-work-order").click()
            await page.wait_for_selector('[data-testid="external-id"]', timeout=settings.rpa_timeout_ms)
            external_id = (await page.get_by_test_id("external-id").inner_text()).strip()
            steps[-1]["status"] = "ok"

            path = artifact_path(root, "success", payload.work_order_id)
            await page.screenshot(path=str(path), full_page=True)
            return RpaWorkOrderResponse(
                success=True,
                external_id=external_id,
                screenshot_path=public_artifact_path(path),
                steps=steps,
            )
        except PlaywrightTimeoutError as exc:
            if steps:
                steps[-1]["status"] = "failed"
            path = artifact_path(root, "failure", payload.work_order_id)
            await page.screenshot(path=str(path), full_page=True)
            return RpaWorkOrderResponse(
                success=False,
                external_id=None,
                screenshot_path=public_artifact_path(path),
                steps=steps,
                error_code="RPA_TIMEOUT",
                error_message=f"{exc.__class__.__name__}: browser operation timed out",
            )
        except Exception as exc:
            if steps:
                steps[-1]["status"] = "failed"
            path = artifact_path(root, "failure", payload.work_order_id)
            try:
                await page.screenshot(path=str(path), full_page=True)
                screenshot_path = public_artifact_path(path)
            except Exception:
                screenshot_path = None
            return RpaWorkOrderResponse(
                success=False,
                external_id=None,
                screenshot_path=screenshot_path,
                steps=steps,
                error_code="RPA_FAILED",
                error_message=f"{exc.__class__.__name__}: browser workflow failed",
            )
        finally:
            await context.close()
            await browser.close()
