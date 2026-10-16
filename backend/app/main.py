from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine

# Import models so SQLAlchemy registers all tables with Base.metadata
import app.models.relational  # noqa: F401

from app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle.

    Startup:
        Creates database tables if they do not already exist.

    Shutdown:
        Closes the database engine.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# Development configuration.
# We will restrict this to the actual frontend origin before deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
# All versioned API routes are registered centrally through api_router.
app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
)


# ---------------------------------------------------------------------------
# Root & Health
# ---------------------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Welcome to Palmistry & Tarot Intelligence Platform API"
    }


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "operational",
        "project": settings.PROJECT_NAME,
    }