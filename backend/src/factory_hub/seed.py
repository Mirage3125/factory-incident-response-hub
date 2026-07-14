import asyncio

from factory_hub.config import get_settings
from factory_hub.database import get_database
from factory_hub.services.core import seed_demo_data


async def main() -> None:
    database = get_database()
    try:
        async with database.session_factory() as session:
            await seed_demo_data(session, get_settings())
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
