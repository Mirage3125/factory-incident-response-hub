import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from factory_hub.config import get_settings
from factory_hub.database import get_database
from factory_hub.main import create_app
from factory_hub.services.core import seed_demo_data


TABLES = [
    "knowledge_cases",
    "rpa_runs",
    "notifications",
    "workflow_events",
    "approvals",
    "work_orders",
    "incident_analysis_runs",
    "incidents",
    "maintenance_records",
    "production_batches",
    "equipment",
    "production_lines",
]


@pytest.fixture()
async def db_session():
    database = get_database()
    async with database.session_factory() as session:
        await session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        await session.execute(text("ALTER SEQUENCE incident_no_seq RESTART WITH 1"))
        await session.execute(text("ALTER SEQUENCE work_order_no_seq RESTART WITH 1"))
        await session.commit()
        await seed_demo_data(session, get_settings())
        yield session
        await session.rollback()
        await session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        await session.execute(text("ALTER SEQUENCE incident_no_seq RESTART WITH 1"))
        await session.execute(text("ALTER SEQUENCE work_order_no_seq RESTART WITH 1"))
        await session.commit()
        await seed_demo_data(session, get_settings())
    await database.dispose()


@pytest.fixture()
async def api_client(db_session):
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
