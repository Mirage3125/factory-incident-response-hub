from fastapi import Header, HTTPException

from factory_hub.config import get_settings


async def require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    if x_internal_token != get_settings().internal_service_token:
        raise HTTPException(status_code=401, detail="invalid_internal_token")
