import os
import sys
from pathlib import Path
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


# ============================================================
# Make backend/ available as the Python import root
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ============================================================
# Application imports
# ============================================================

from app.core.database import Base, get_db
from app.main import app


# ============================================================
# Test database configuration
# ============================================================

TEST_DATABASE_URL = os.getenv(
    "TEST_POSTGRES_ASYNC_URI"
)

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_POSTGRES_ASYNC_URI is not configured. "
        "Refusing to run tests against the normal application "
        "database."
    )


# ============================================================
# Safety check
# ============================================================

if "palmistry_tarot_test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_POSTGRES_ASYNC_URI does not point to the "
        "palmistry_tarot_test database. "
        "Refusing to run tests."
    )


# ============================================================
# Test database engine
# ============================================================

# NullPool is intentional here.
#
# pytest-asyncio uses separate event loops for function-scoped
# async tests. Reusing an asyncpg connection from another loop
# can cause Windows ProactorEventLoop errors such as:
#
#     AttributeError: 'NoneType' object has no attribute 'send'
#
# NullPool creates a fresh database connection instead of
# reusing connections across event loops.

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)


TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ============================================================
# Database lifecycle
# ============================================================

@pytest_asyncio.fixture(
    scope="session",
    autouse=True,
)
async def prepare_test_database() -> AsyncGenerator[
    None,
    None,
]:
    """
    Create all application tables in the dedicated test
    database before the test session.
    """

    async with test_engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

    yield

    async with test_engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.drop_all
        )

    await test_engine.dispose()


# ============================================================
# Clean test data before every test
# ============================================================

@pytest_asyncio.fixture(autouse=True)
async def clean_test_data() -> AsyncGenerator[
    None,
    None,
]:
    """
    Remove data created by previous tests.

    API endpoints commit their own transactions, so a normal
    fixture rollback cannot undo those commits.
    """

    async with test_engine.begin() as connection:
        await connection.execute(
            text(
                """
                TRUNCATE TABLE
                    reports,
                    payments,
                    readings,
                    profiles,
                    users
                RESTART IDENTITY CASCADE
                """
            )
        )

    yield


# ============================================================
# Database session fixture
# ============================================================

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[
    AsyncSession,
    None,
]:
    """
    Provide an asynchronous database session for tests.
    """

    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ============================================================
# FastAPI client fixture
# ============================================================

@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[
    AsyncClient,
    None,
]:
    """
    Provide an asynchronous HTTP client connected to the
    FastAPI application.

    FastAPI's get_db dependency is overridden so API requests
    use the dedicated test database.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[
        get_db
    ] = override_get_db

    transport = ASGITransport(
        app=app,
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()