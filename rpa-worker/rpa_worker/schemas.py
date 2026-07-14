from typing import Any

from pydantic import BaseModel, Field


class RpaWorkOrderRequest(BaseModel):
    work_order_id: int
    incident_no: str = Field(min_length=1, max_length=80)
    equipment_code: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    priority: str = Field(min_length=1, max_length=10)
    description: str = Field(min_length=1, max_length=4000)
    assigned_team: str = Field(min_length=1, max_length=120)
    reason: str | None = None


class RpaWorkOrderResponse(BaseModel):
    success: bool
    external_id: str | None = None
    screenshot_path: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
