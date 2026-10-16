from uuid import UUID

import pytest
from jose import jwt
from sqlalchemy import select

from app.core.config import settings
from app.models.relational import Profile, User


# ============================================================
# Signup Tests
# ============================================================


@pytest.mark.asyncio
async def test_signup_success(client, db_session):
    """
    A valid user should be registered successfully.

    The test verifies:
    - HTTP 201 response
    - returned user information
    - default User role
    - password is not returned
    - Profile is created
    """

    payload = {
        "email": "testuser@example.com",
        "password": "TestPassword123",
    }

    response = await client.post(
        "/api/v1/auth/signup",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "testuser@example.com"
    assert data["role"] == "User"
    assert "password" not in data
    assert "password_hash" not in data

    user_id = UUID(data["id"])

    result = await db_session.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    assert user is not None
    assert user.email == "testuser@example.com"
    assert user.role == "User"

    # Verify that a Profile was created.
    profile_result = await db_session.execute(
        select(Profile).where(
            Profile.user_id == user.id
        )
    )

    profile = profile_result.scalar_one_or_none()

    assert profile is not None
    assert profile.user_id == user.id


# ============================================================
# Duplicate Signup
# ============================================================


@pytest.mark.asyncio
async def test_signup_duplicate_email(client):
    """
    Registering the same email twice should fail.
    """

    payload = {
        "email": "duplicate@example.com",
        "password": "TestPassword123",
    }

    first_response = await client.post(
        "/api/v1/auth/signup",
        json=payload,
    )

    assert first_response.status_code == 201

    second_response = await client.post(
        "/api/v1/auth/signup",
        json=payload,
    )

    assert second_response.status_code == 400

    data = second_response.json()

    assert (
        data["detail"]
        == "A user with this email already exists."
    )


# ============================================================
# Email Normalization
# ============================================================


@pytest.mark.asyncio
async def test_signup_normalizes_email(client):
    """
    Signup should normalize the email address to lowercase.
    """

    payload = {
        "email": "TestUser@Example.COM",
        "password": "TestPassword123",
    }

    response = await client.post(
        "/api/v1/auth/signup",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "testuser@example.com"


# ============================================================
# Password Validation
# ============================================================


@pytest.mark.asyncio
async def test_signup_rejects_short_password(client):
    """
    Passwords shorter than the schema minimum should be rejected.
    """

    payload = {
        "email": "shortpassword@example.com",
        "password": "123",
    }

    response = await client.post(
        "/api/v1/auth/signup",
        json=payload,
    )

    assert response.status_code == 422


# ============================================================
# Login Tests
# ============================================================


@pytest.mark.asyncio
async def test_login_success(client):
    """
    A registered user should be able to log in successfully.
    """

    signup_payload = {
        "email": "loginuser@example.com",
        "password": "LoginPassword123",
    }

    signup_response = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload,
    )

    assert signup_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "loginuser@example.com",
            "password": "LoginPassword123",
        },
    )

    assert login_response.status_code == 200

    data = login_response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0


# ============================================================
# Wrong Password
# ============================================================


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """
    An incorrect password should return 401.
    """

    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "wrongpassword@example.com",
            "password": "CorrectPassword123",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "wrongpassword@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == "Incorrect email or password"

    assert (
        response.headers.get("WWW-Authenticate")
        == "Bearer"
    )


# ============================================================
# Unknown User
# ============================================================


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    """
    Logging in with an email that does not exist should
    return the same generic authentication error.
    """

    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "doesnotexist@example.com",
            "password": "SomePassword123",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == "Incorrect email or password"


# ============================================================
# JWT Validation
# ============================================================


@pytest.mark.asyncio
async def test_login_returns_valid_jwt(client):
    """
    The returned access token should be a valid JWT containing
    a user subject and expiration claim.
    """

    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "jwtuser@example.com",
            "password": "JwtPassword123",
        },
    )

    assert signup_response.status_code == 201

    user_id = signup_response.json()["id"]

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "jwtuser@example.com",
            "password": "JwtPassword123",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )

    assert payload["sub"] == user_id
    assert "exp" in payload


# ============================================================
# Case-Insensitive Login
# ============================================================


@pytest.mark.asyncio
async def test_login_normalizes_email(client):
    """
    Email normalization should also work during login.
    """

    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "caseuser@example.com",
            "password": "CasePassword123",
        },
    )

    assert signup_response.status_code == 201

    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "CASEUSER@EXAMPLE.COM",
            "password": "CasePassword123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"