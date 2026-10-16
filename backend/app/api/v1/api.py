from fastapi import APIRouter
from app.api.v1.endpoints import spiritual_consultant
from app.api.v1.endpoints import consultation_notes
from app.api.v1.endpoints import consultation_hub

from app.api.v1.endpoints import (
    auth,
    users,
    roles_demo,
    palm,
    tarot,
    readings,
    tarot_reader,
    admin,
)


api_router = APIRouter()


# ---------------------------------------------------------------------------
# Authentication & User Management
# ---------------------------------------------------------------------------
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["User Profiles"],
)


# ---------------------------------------------------------------------------
# Role-Based Access Control
# ---------------------------------------------------------------------------
api_router.include_router(
    roles_demo.router,
    prefix="/roles",
    tags=["Role-Based Access Control"],
)


# ---------------------------------------------------------------------------
# Palmistry
# ---------------------------------------------------------------------------
api_router.include_router(
    palm.router,
    prefix="/palm",
    tags=["Palmistry Engine"],
)


# ---------------------------------------------------------------------------
# Tarot
# ---------------------------------------------------------------------------
api_router.include_router(
    tarot.router,
    prefix="/tarot",
    tags=["Tarot Engine"],
)


# ---------------------------------------------------------------------------
# Reading & Intelligence Workflows
# ---------------------------------------------------------------------------
api_router.include_router(
    readings.router,
    prefix="/readings",
    tags=["Reading & Intelligence"],
)

api_router.include_router(
    tarot_reader.router,
    prefix="/tarot-reader",
    tags=["Tarot Reader Workspace"],
)

api_router.include_router(
    spiritual_consultant.router,
    prefix="/spiritual-consultant",
    tags=["Spiritual Consultant Workspace"],
)

api_router.include_router(
    consultation_notes.router,
    prefix="/consultation-notes",
    tags=["Consultation Notes"],
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Administration"],
)

api_router.include_router(
    consultation_hub.router,
    prefix="/consultation-hub",
    tags=["Consultation Hub"],
)