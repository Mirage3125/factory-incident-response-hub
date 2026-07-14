from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from factory_hub.config import Settings, get_settings
from factory_hub.database import Database, get_database
from factory_hub.logging import configure_logging
from factory_hub.api.routes import internal_router, router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    app = FastAPI(title="Factory Incident Response Hub API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(database: Database = Depends(get_database)) -> dict[str, str]:
        try:
            await database.ping()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="database_unavailable") from exc
        return {"status": "ready"}

    app.include_router(router)
    app.include_router(internal_router)

    return app


app = create_app()
