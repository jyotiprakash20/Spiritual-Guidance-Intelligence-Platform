import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, require_roles
from app.models.relational import User
from app.schemas.user import UserRole


# ============================================================
# Test App
# ============================================================

def create_test_app(allowed_roles):
    """
    Create a tiny FastAPI application using the real
    require_roles() dependency.

    This lets us test the RBAC logic directly without
    creating a fake production endpoint.
    """

    app = FastAPI()

    @app.get("/protected")
    async def protected_endpoint(
        current_user: User = Depends(
            require_roles(allowed_roles)
        ),
    ):
        return {
            "status": "success",
            "email": current_user.email,
            "role": current_user.role,
        }

    return app


# ============================================================
# Helpers
# ============================================================

async def create_user(db, email: str, role: str):
    """
    Create a user directly in the test database.
    """

    user = User(
        email=email,
        password_hash="test-password-hash",
        role=role,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def override_current_user(app, user):
    """
    Override authentication so the RBAC dependency receives
    a specific test user.

    This isolates role authorization from JWT/authentication
    tests.
    """

    async def override():
        return user

    app.dependency_overrides[get_current_user] = override


async def call_protected_endpoint(app):
    """
    Call the temporary protected endpoint.
    """

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.get("/protected")


# ============================================================
# USER ROLE
# ============================================================

@pytest.mark.asyncio
async def test_user_allowed_role(db_session):
    """
    A normal User should be allowed when User is included
    in the allowed roles.
    """

    user = await create_user(
        db_session,
        "user@test.com",
        UserRole.USER.value,
    )

    app = create_test_app(
        [UserRole.USER]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["role"] == UserRole.USER.value
    assert data["email"] == "user@test.com"


@pytest.mark.asyncio
async def test_user_forbidden_for_tarot_reader_endpoint(db_session):
    """
    A normal User should receive 403 when the endpoint
    requires Tarot Reader.
    """

    user = await create_user(
        db_session,
        "user-forbidden@test.com",
        UserRole.USER.value,
    )

    app = create_test_app(
        [UserRole.TAROT_READER]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 403

    data = response.json()

    assert "Access forbidden" in data["detail"]
    assert UserRole.TAROT_READER.value in data["detail"]


# ============================================================
# TAROT READER
# ============================================================

@pytest.mark.asyncio
async def test_tarot_reader_allowed(db_session):
    """
    Tarot Reader should be allowed to access a Tarot Reader
    protected endpoint.
    """

    user = await create_user(
        db_session,
        "tarot-reader@test.com",
        UserRole.TAROT_READER.value,
    )

    app = create_test_app(
        [UserRole.TAROT_READER]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 200

    data = response.json()

    assert data["role"] == UserRole.TAROT_READER.value


@pytest.mark.asyncio
async def test_tarot_reader_forbidden_for_spiritual_consultant_endpoint(
    db_session,
):
    """
    Tarot Reader should not be allowed when only Spiritual
    Consultant is permitted.
    """

    user = await create_user(
        db_session,
        "tarot-forbidden@test.com",
        UserRole.TAROT_READER.value,
    )

    app = create_test_app(
        [UserRole.SPIRITUAL_CONSULTANT]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 403


# ============================================================
# SPIRITUAL CONSULTANT
# ============================================================

@pytest.mark.asyncio
async def test_spiritual_consultant_allowed(db_session):
    """
    Spiritual Consultant should be allowed when explicitly
    included in the allowed roles.
    """

    user = await create_user(
        db_session,
        "consultant@test.com",
        UserRole.SPIRITUAL_CONSULTANT.value,
    )

    app = create_test_app(
        [UserRole.SPIRITUAL_CONSULTANT]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 200

    data = response.json()

    assert data["role"] == UserRole.SPIRITUAL_CONSULTANT.value


@pytest.mark.asyncio
async def test_spiritual_consultant_forbidden_for_user_endpoint(
    db_session,
):
    """
    Spiritual Consultant should not automatically receive
    access to an endpoint restricted to User.
    """

    user = await create_user(
        db_session,
        "consultant-forbidden@test.com",
        UserRole.SPIRITUAL_CONSULTANT.value,
    )

    app = create_test_app(
        [UserRole.USER]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 403


# ============================================================
# ADMINISTRATOR BYPASS
# ============================================================

@pytest.mark.asyncio
async def test_administrator_can_access_user_endpoint(db_session):
    """
    Administrator should bypass a User-only restriction.
    """

    user = await create_user(
        db_session,
        "admin-user@test.com",
        UserRole.ADMIN.value,
    )

    app = create_test_app(
        [UserRole.USER]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 200

    data = response.json()

    assert data["role"] == UserRole.ADMIN.value


@pytest.mark.asyncio
async def test_administrator_can_access_tarot_endpoint(db_session):
    """
    Administrator should bypass a Tarot Reader restriction.
    """

    user = await create_user(
        db_session,
        "admin-tarot@test.com",
        UserRole.ADMIN.value,
    )

    app = create_test_app(
        [UserRole.TAROT_READER]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_administrator_can_access_consultant_endpoint(
    db_session,
):
    """
    Administrator should bypass a Spiritual Consultant
    restriction.
    """

    user = await create_user(
        db_session,
        "admin-consultant@test.com",
        UserRole.ADMIN.value,
    )

    app = create_test_app(
        [UserRole.SPIRITUAL_CONSULTANT]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 200


# ============================================================
# MULTIPLE ALLOWED ROLES
# ============================================================

@pytest.mark.asyncio
async def test_multiple_allowed_roles(db_session):
    """
    A user should be allowed when their role is one of
    several permitted roles.
    """

    user = await create_user(
        db_session,
        "multi-role@test.com",
        UserRole.TAROT_READER.value,
    )

    app = create_test_app(
        [
            UserRole.USER,
            UserRole.TAROT_READER,
        ]
    )

    await override_current_user(app, user)

    response = await call_protected_endpoint(app)

    assert response.status_code == 200

    data = response.json()

    assert data["role"] == UserRole.TAROT_READER.value


# ============================================================
# AUTHENTICATION FAILURE
# ============================================================

@pytest.mark.asyncio
async def test_protected_endpoint_requires_authentication():
    """
    Without authentication, the real get_current_user
    dependency should reject the request.
    """

    app = create_test_app(
        [UserRole.USER]
    )

    transport = ASGITransport(app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/protected")

    assert response.status_code == 401


# ============================================================
# ROLE ENUM VALIDATION
# ============================================================

def test_all_expected_roles_exist():
    """
    Verify that the four project roles are defined exactly
    as expected.
    """

    assert UserRole.USER.value == "User"

    assert (
        UserRole.TAROT_READER.value
        == "Tarot Reader"
    )

    assert (
        UserRole.SPIRITUAL_CONSULTANT.value
        == "Spiritual Consultant"
    )

    assert (
        UserRole.ADMIN.value
        == "Administrator"
    )


def test_role_enum_contains_exactly_four_roles():
    """
    Ensure no unexpected role has been added accidentally.
    """

    roles = list(UserRole)

    assert len(roles) == 4

    assert set(roles) == {
        UserRole.USER,
        UserRole.TAROT_READER,
        UserRole.SPIRITUAL_CONSULTANT,
        UserRole.ADMIN,
    }