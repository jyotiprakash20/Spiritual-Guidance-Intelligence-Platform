from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings


# ============================================================
# PostgreSQL / SQLAlchemy
# ============================================================

engine = create_async_engine(
    settings.POSTGRES_ASYNC_URI,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an asynchronous PostgreSQL database session
    to FastAPI route handlers.
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ============================================================
# MongoDB
# ============================================================

mongo_client = AsyncIOMotorClient(
    settings.MONGO_URI,
)

mongo_db = mongo_client[
    settings.MONGO_DB_NAME
]


# ============================================================
# Redis
# ============================================================

redis_client = aioredis.from_url(
    settings.REDIS_URI,
    decode_responses=True,
)


# ============================================================
# Shutdown helpers
# ============================================================

async def close_database_connections() -> None:
    """
    Close PostgreSQL, MongoDB, and Redis connections.
    """

    await engine.dispose()

    mongo_client.close()

    await redis_client.aclose()