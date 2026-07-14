from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from rpa_worker.runner import run_work_order_rpa
from rpa_worker.schemas import RpaWorkOrderRequest, RpaWorkOrderResponse


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    internal_service_token: str = Field(default="change-me-in-local-env", alias="INTERNAL_SERVICE_TOKEN")
    legacy_mes_url: str = Field(default="http://legacy-mes:8300", alias="LEGACY_MES_URL")
    mes_username: str = Field(default="mes-demo", alias="MES_DEMO_USERNAME")
    mes_password: str = Field(default="mes-password", alias="MES_DEMO_PASSWORD")
    rpa_headless: bool = Field(default=True, alias="RPA_HEADLESS")
    rpa_timeout_ms: int = Field(default=10000, alias="RPA_TIMEOUT_MS")
    rpa_artifact_root: str = Field(default="/artifacts/rpa", alias="RPA_ARTIFACT_ROOT")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def require_internal_token(x_internal_token: Annotated[str | None, Header()] = None, settings: Settings = Depends(get_settings)) -> None:
    if x_internal_token != settings.internal_service_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_internal_token")


app = FastAPI(title="RPA Worker", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/internal/rpa/work-orders", response_model=RpaWorkOrderResponse, dependencies=[Depends(require_internal_token)])
async def create_work_order(payload: RpaWorkOrderRequest, settings: Settings = Depends(get_settings)) -> RpaWorkOrderResponse:
    return await run_work_order_rpa(settings, payload)
