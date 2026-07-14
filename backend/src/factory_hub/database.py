from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from factory_hub.config import Settings, get_settings
from factory_hub.domain.models import Base


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()


def get_database() -> Database:
    return Database(get_settings())


async def get_session() -> AsyncIterator[AsyncSession]:
    active_database = get_database()
    async with active_database.session_factory() as session:
        try:
            yield session
        finally:
            await active_database.dispose()


async def lifespan_database() -> AsyncIterator[Database]:
    database = get_database()
    try:
        yield database
    finally:
        await database.dispose()
