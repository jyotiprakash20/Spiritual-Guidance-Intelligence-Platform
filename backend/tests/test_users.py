import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.relational import User, Profile


# -------------------------------------------------------------------
# GET CURRENT USER PROFILE
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_user_profile(
    client: AsyncClient,
    db_session,
):
    """
    Authenticated user should be able to retrieve
    their complete profile.
    """

    email = "profile_get@example.com"
    password = "password123"

    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": password,
        },
    )

    assert signup_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == email
    assert "profile" in data


# -------------------------------------------------------------------
# GET PROFILE WITHOUT AUTHENTICATION
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_profile_requires_authentication(
    client: AsyncClient,
):
    """
    Profile endpoint should reject unauthenticated requests.
    """

    response = await client.get(
        "/api/v1/users/me"
    )

    assert response.status_code == 401


# -------------------------------------------------------------------
# UPDATE PROFILE
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_profile_success(
    client: AsyncClient,
    db_session,
):
    """
    User should be able to create/update their profile.
    """

    email = "profile_update@example.com"
    password = "password123"

    # ---------------------------------------------------------------
    # Create user
    # ---------------------------------------------------------------

    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": password,
        },
    )

    assert signup_response.status_code == 201

    # ---------------------------------------------------------------
    # Login
    # ---------------------------------------------------------------

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    # ---------------------------------------------------------------
    # Update profile
    # ---------------------------------------------------------------

    response = await client.put(
        "/api/v1/users/me/profile",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "full_name": "Test User",
            "age_group": "21-30",
            "interests": "Tarot, AI, Technology",
            "spiritual_goals": "Personal growth",
        },
    )

    assert response.status_code == 200

    data = response.json()

    # ---------------------------------------------------------------
    # Verify API response
    # ---------------------------------------------------------------

    assert data["full_name"] == "Test User"
    assert data["age_group"] == "21-30"
    assert data["interests"] == "Tarot, AI, Technology"
    assert data["spiritual_goals"] == "Personal growth"

    # ---------------------------------------------------------------
    # Verify user exists in database
    # ---------------------------------------------------------------

    user_result = await db_session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = user_result.scalar_one_or_none()

    assert user is not None

    # ---------------------------------------------------------------
    # Verify profile exists in database
    # ---------------------------------------------------------------

    profile_result = await db_session.execute(
        select(Profile).where(
            Profile.user_id == user.id
        )
    )

    profile = profile_result.scalar_one_or_none()

    assert profile is not None

    # ---------------------------------------------------------------
    # Verify persisted profile values
    # ---------------------------------------------------------------

    assert profile.full_name == "Test User"
    assert profile.age_group == "21-30"
    assert profile.interests == "Tarot, AI, Technology"
    assert profile.spiritual_goals == "Personal growth"


# -------------------------------------------------------------------
# PARTIAL PROFILE UPDATE
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_profile_partial_update(
    client: AsyncClient,
):
    """
    Only supplied profile fields should be changed.
    """

    email = "profile_partial@example.com"
    password = "password123"

    # ---------------------------------------------------------------
    # Create user
    # ---------------------------------------------------------------

    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": password,
        },
    )

    assert signup_response.status_code == 201

    # ---------------------------------------------------------------
    # Login
    # ---------------------------------------------------------------

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    # ---------------------------------------------------------------
    # First update
    # ---------------------------------------------------------------

    first_update = await client.put(
        "/api/v1/users/me/profile",
        headers=headers,
        json={
            "full_name": "Original Name",
            "interests": "Programming",
        },
    )

    assert first_update.status_code == 200

    # ---------------------------------------------------------------
    # Partial update
    # ---------------------------------------------------------------

    second_update = await client.put(
        "/api/v1/users/me/profile",
        headers=headers,
        json={
            "full_name": "Updated Name",
        },
    )

    assert second_update.status_code == 200

    data = second_update.json()

    # ---------------------------------------------------------------
    # Verify changed field
    # ---------------------------------------------------------------

    assert data["full_name"] == "Updated Name"

    # ---------------------------------------------------------------
    # Verify existing field was preserved
    # ---------------------------------------------------------------

    assert data["interests"] == "Programming"


# -------------------------------------------------------------------
# UPDATE PROFILE WITHOUT AUTHENTICATION
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_profile_requires_authentication(
    client: AsyncClient,
):
    """
    Profile update should reject unauthenticated requests.
    """

    response = await client.put(
        "/api/v1/users/me/profile",
        json={
            "full_name": "Unauthorized User",
        },
    )

    assert response.status_code == 401


# -------------------------------------------------------------------
# UPDATE USER PREFERENCES
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_preferences_success(
    client: AsyncClient,
):
    """
    Authenticated user should be able to update preferences.
    """

    email = "preferences@example.com"
    password = "password123"

    # ---------------------------------------------------------------
    # Create user
    # ---------------------------------------------------------------

    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": password,
        },
    )

    assert signup_response.status_code == 201

    # ---------------------------------------------------------------
    # Login
    # ---------------------------------------------------------------

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    # ---------------------------------------------------------------
    # Update preferences
    # ---------------------------------------------------------------

    response = await client.put(
        "/api/v1/users/me/preferences",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "preferences": {
                "theme": "dark",
                "notifications": True,
                "language": "en",
            }
        },
    )

    assert response.status_code == 200

    data = response.json()

    # ---------------------------------------------------------------
    # Verify response
    # ---------------------------------------------------------------

    assert data["preferences"]["theme"] == "dark"
    assert data["preferences"]["notifications"] is True
    assert data["preferences"]["language"] == "en"


# -------------------------------------------------------------------
# UPDATE PREFERENCES WITHOUT AUTHENTICATION
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preferences_require_authentication(
    client: AsyncClient,
):
    """
    Preferences endpoint should reject unauthenticated requests.
    """

    response = await client.put(
        "/api/v1/users/me/preferences",
        json={
            "preferences": {
                "theme": "dark",
            }
        },
    )

    assert response.status_code == 401