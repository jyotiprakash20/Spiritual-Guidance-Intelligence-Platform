import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.api.v1.endpoints.roles_demo import router
from app.models.relational import User
from app.schemas.user import UserRole


# ============================================================
# Test Application
# ============================================================

def create_roles_test_app():
    """
    Create a small FastAPI application using the real
    roles_demo router.

    This allows us to test the actual RBAC endpoints without
    modifying the production application.
    """

    app = FastAPI()

    app.include_router(
        router,
        prefix="/roles",
    )

    return app


# ============================================================
# Helpers
# ============================================================

def create_test_user(
    email: str,
    role: str,
) -> User:
    """
    Create an in-memory User object.

    No database record is required because the authentication
    dependency is overridden for these endpoint tests.
    """

    return User(
        email=email,
        password_hash="test-password-hash",
        role=role,
    )


async def override_current_user(
    app: FastAPI,
    user: User,
):
    """
    Make the real roles_demo endpoints receive the supplied
    test user as the authenticated user.
    """

    async def override():
        return user

    app.dependency_overrides[get_current_user] = override


async def request_endpoint(
    app: FastAPI,
    endpoint: str,
):
    """
    Send a GET request to a roles endpoint.
    """

    transport = ASGITransport(app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.get(endpoint)


# ============================================================
# USER AREA
# ============================================================

@pytest.mark.asyncio
async def test_user_area_allows_authenticated_user():
    """
    Any authenticated user should be able to access
    /roles/user-area.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "user-area@test.com",
        UserRole.USER.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/user-area",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Welcome to the Seeker area"
    assert data["user_email"] == "user-area@test.com"
    assert data["role"] == UserRole.USER.value


@pytest.mark.asyncio
async def test_user_area_allows_tarot_reader():
    """
    User area only requires authentication, so a Tarot Reader
    should also be able to access it.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "reader-user-area@test.com",
        UserRole.TAROT_READER.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/user-area",
    )

    assert response.status_code == 200
    assert response.json()["role"] == UserRole.TAROT_READER.value


@pytest.mark.asyncio
async def test_user_area_allows_spiritual_consultant():
    """
    Spiritual Consultant should also be able to access the
    authenticated user area.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "consultant-user-area@test.com",
        UserRole.SPIRITUAL_CONSULTANT.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/user-area",
    )

    assert response.status_code == 200
    assert response.json()["role"] == UserRole.SPIRITUAL_CONSULTANT.value


# ============================================================
# TAROT READER WORKSPACE
# ============================================================

@pytest.mark.asyncio
async def test_tarot_reader_workspace_allows_tarot_reader():
    """
    Tarot Reader should be allowed into the Tarot Reader
    workspace.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "tarot-reader@test.com",
        UserRole.TAROT_READER.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/tarot-reader-workspace",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Welcome to the Tarot Reading Desk"
    assert data["user_email"] == "tarot-reader@test.com"
    assert data["role"] == UserRole.TAROT_READER.value


@pytest.mark.asyncio
async def test_tarot_reader_workspace_rejects_normal_user():
    """
    Normal User should not be allowed into the Tarot Reader
    workspace.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "normal-user@test.com",
        UserRole.USER.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/tarot-reader-workspace",
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tarot_reader_workspace_rejects_spiritual_consultant():
    """
    Spiritual Consultant should not be allowed into the
    Tarot Reader workspace.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "consultant-tarot@test.com",
        UserRole.SPIRITUAL_CONSULTANT.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/tarot-reader-workspace",
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tarot_reader_workspace_allows_administrator():
    """
    Administrator should bypass the Tarot Reader role
    restriction.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "admin-tarot@test.com",
        UserRole.ADMIN.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/tarot-reader-workspace",
    )

    assert response.status_code == 200
    assert response.json()["role"] == UserRole.ADMIN.value


# ============================================================
# SPIRITUAL CONSULTANT WORKSPACE
# ============================================================

@pytest.mark.asyncio
async def test_spiritual_consultant_workspace_allows_consultant():
    """
    Spiritual Consultant should be allowed into the
    Spiritual Consultation Suite.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "consultant@test.com",
        UserRole.SPIRITUAL_CONSULTANT.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/spiritual-consultant-workspace",
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["message"]
        == "Welcome to the Spiritual Consultation Suite"
    )
    assert data["user_email"] == "consultant@test.com"
    assert data["role"] == UserRole.SPIRITUAL_CONSULTANT.value


@pytest.mark.asyncio
async def test_spiritual_consultant_workspace_rejects_normal_user():
    """
    Normal User should not be allowed into the Spiritual
    Consultant workspace.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "normal-consultant@test.com",
        UserRole.USER.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/spiritual-consultant-workspace",
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_spiritual_consultant_workspace_rejects_tarot_reader():
    """
    Tarot Reader should not be allowed into the Spiritual
    Consultant workspace.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "reader-consultant@test.com",
        UserRole.TAROT_READER.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/spiritual-consultant-workspace",
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_spiritual_consultant_workspace_allows_administrator():
    """
    Administrator should bypass the Spiritual Consultant
    role restriction.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "admin-consultant@test.com",
        UserRole.ADMIN.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/spiritual-consultant-workspace",
    )

    assert response.status_code == 200
    assert response.json()["role"] == UserRole.ADMIN.value


# ============================================================
# ADMIN PANEL
# ============================================================

@pytest.mark.asyncio
async def test_admin_panel_allows_administrator():
    """
    Only Administrator should be allowed into the Admin Panel.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "administrator@test.com",
        UserRole.ADMIN.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/admin-panel",
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["message"]
        == "Welcome to the Master Administration Console"
    )
    assert data["user_email"] == "administrator@test.com"
    assert data["role"] == UserRole.ADMIN.value


@pytest.mark.asyncio
async def test_admin_panel_rejects_normal_user():
    """
    Normal User should not be allowed into the Admin Panel.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "user-admin-panel@test.com",
        UserRole.USER.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/admin-panel",
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_panel_rejects_tarot_reader():
    """
    Tarot Reader should not be allowed into the Admin Panel.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "reader-admin-panel@test.com",
        UserRole.TAROT_READER.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/admin-panel",
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_panel_rejects_spiritual_consultant():
    """
    Spiritual Consultant should not be allowed into the
    Admin Panel.
    """

    app = create_roles_test_app()

    user = create_test_user(
        "consultant-admin-panel@test.com",
        UserRole.SPIRITUAL_CONSULTANT.value,
    )

    await override_current_user(app, user)

    response = await request_endpoint(
        app,
        "/roles/admin-panel",
    )

    assert response.status_code == 403


# ============================================================
# AUTHENTICATION
# ============================================================

@pytest.mark.asyncio
async def test_user_area_requires_authentication():
    """
    The real user-area endpoint should reject unauthenticated
    requests.
    """

    app = create_roles_test_app()

    response = await request_endpoint(
        app,
        "/roles/user-area",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tarot_reader_workspace_requires_authentication():
    """
    The real Tarot Reader workspace should reject
    unauthenticated requests.
    """

    app = create_roles_test_app()

    response = await request_endpoint(
        app,
        "/roles/tarot-reader-workspace",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_spiritual_consultant_workspace_requires_authentication():
    """
    The real Spiritual Consultant workspace should reject
    unauthenticated requests.
    """

    app = create_roles_test_app()

    response = await request_endpoint(
        app,
        "/roles/spiritual-consultant-workspace",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_panel_requires_authentication():
    """
    The real Admin Panel should reject unauthenticated
    requests.
    """

    app = create_roles_test_app()

    response = await request_endpoint(
        app,
        "/roles/admin-panel",
    )

    assert response.status_code == 401