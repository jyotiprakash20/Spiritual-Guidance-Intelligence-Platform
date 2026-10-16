import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.relational import User, Reading


# -------------------------------------------------------------------
# HELPER: CREATE USER + LOGIN
# -------------------------------------------------------------------

async def create_authenticated_user(
    client: AsyncClient,
    email: str,
    password: str = "password123",
):
    """
    Create a test user and return the JWT access token.
    """

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

    data = login_response.json()

    assert "access_token" in data

    return data["access_token"]


# -------------------------------------------------------------------
# AUTHENTICATION
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_draw_requires_authentication(
    client: AsyncClient,
):
    """
    Tarot drawing must reject unauthenticated requests.
    """

    response = await client.post(
        "/api/v1/tarot/draw"
    )

    assert response.status_code == 401


# -------------------------------------------------------------------
# DEFAULT THREE-CARD SPREAD
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_default_three_card_spread(
    client: AsyncClient,
    db_session,
):
    """
    The default Tarot spread should be three_card.
    """

    email = "tarot_default@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    response = await client.post(
        "/api/v1/tarot/draw",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert "reading_id" in data
    assert "tarot" in data

    tarot = data["tarot"]

    assert tarot["spread_type"] == "three_card"
    assert "cards" in tarot
    assert len(tarot["cards"]) == 3


# -------------------------------------------------------------------
# SINGLE-CARD SPREAD
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_single_card_spread(
    client: AsyncClient,
):
    """
    Single-card spread should return exactly one card.
    """

    token = await create_authenticated_user(
        client,
        "tarot_single@example.com",
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=single",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"

    tarot = data["tarot"]

    assert tarot["spread_type"] == "single"
    assert len(tarot["cards"]) == 1


# -------------------------------------------------------------------
# RELATIONSHIP SPREAD
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_relationship_spread(
    client: AsyncClient,
):
    """
    Relationship spread should generate four cards.
    """

    token = await create_authenticated_user(
        client,
        "tarot_relationship@example.com",
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=relationship",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"

    tarot = data["tarot"]

    assert tarot["spread_type"] == "relationship"
    assert len(tarot["cards"]) == 4


# -------------------------------------------------------------------
# CAREER SPREAD
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_career_spread(
    client: AsyncClient,
):
    """
    Career spread should generate five cards.
    """

    token = await create_authenticated_user(
        client,
        "tarot_career@example.com",
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=career",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"

    tarot = data["tarot"]

    assert tarot["spread_type"] == "career"
    assert len(tarot["cards"]) == 5


# -------------------------------------------------------------------
# CELTIC CROSS
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_celtic_cross_spread(
    client: AsyncClient,
):
    """
    Celtic Cross should generate ten cards.
    """

    token = await create_authenticated_user(
        client,
        "tarot_celtic@example.com",
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=celtic_cross",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"

    tarot = data["tarot"]

    assert tarot["spread_type"] == "celtic_cross"
    assert len(tarot["cards"]) == 10


# -------------------------------------------------------------------
# LIFE PATH
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_life_path_spread(
    client: AsyncClient,
):
    """
    Life Path spread should generate seven cards.
    """

    token = await create_authenticated_user(
        client,
        "tarot_life_path@example.com",
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=life_path",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"

    tarot = data["tarot"]

    assert tarot["spread_type"] == "life_path"
    assert len(tarot["cards"]) == 7


# -------------------------------------------------------------------
# INVALID SPREAD
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_invalid_spread(
    client: AsyncClient,
):
    """
    Invalid spread types should return HTTP 400.
    """

    token = await create_authenticated_user(
        client,
        "tarot_invalid_spread@example.com",
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=invalid_spread",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert "detail" in data


# -------------------------------------------------------------------
# CASE NORMALIZATION
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_spread_case_normalization(
    client: AsyncClient,
):
    """
    The endpoint should normalize the spread type
    using strip().lower().
    """

    token = await create_authenticated_user(
        client,
        "tarot_case@example.com",
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=THREE_CARD",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["tarot"]["spread_type"] == "three_card"


# -------------------------------------------------------------------
# UNIQUE CARDS
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_cards_are_unique(
    client: AsyncClient,
):
    """
    Cards within a spread should not be duplicated.
    """

    token = await create_authenticated_user(
        client,
        "tarot_unique@example.com",
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=celtic_cross",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    cards = response.json()["tarot"]["cards"]

    # The Tarot service uses `card_id`, not `id`.
    card_ids = [
        card["card_id"]
        for card in cards
    ]

    assert len(card_ids) == len(set(card_ids))


# -------------------------------------------------------------------
# READING DATABASE PERSISTENCE
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_reading_is_saved(
    client: AsyncClient,
    db_session,
):
    """
    A successful Tarot reading should be persisted
    as a TAROT Reading.
    """

    email = "tarot_database@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=three_card",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    reading_id = data["reading_id"]

    result = await db_session.execute(
        select(Reading).where(
            Reading.id == reading_id
        )
    )

    reading = result.scalar_one_or_none()

    assert reading is not None
    assert reading.reading_type == "TAROT"
    assert reading.analysis_data is not None


# -------------------------------------------------------------------
# DATABASE USER ASSOCIATION
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tarot_reading_belongs_to_current_user(
    client: AsyncClient,
    db_session,
):
    """
    The stored Tarot reading must belong to the authenticated user.
    """

    email = "tarot_user_association@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    response = await client.post(
        "/api/v1/tarot/draw?spread_type=single",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    reading_id = response.json()["reading_id"]

    user_result = await db_session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = user_result.scalar_one_or_none()

    assert user is not None

    reading_result = await db_session.execute(
        select(Reading).where(
            Reading.id == reading_id
        )
    )

    reading = reading_result.scalar_one_or_none()

    assert reading is not None
    assert reading.user_id == user.id


# -------------------------------------------------------------------
# MULTIPLE READINGS
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_tarot_readings_are_saved_separately(
    client: AsyncClient,
    db_session,
):
    """
    Multiple Tarot requests should create separate readings.
    """

    email = "tarot_multiple@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    headers = {
        "Authorization": f"Bearer {token}",
    }

    first_response = await client.post(
        "/api/v1/tarot/draw?spread_type=single",
        headers=headers,
    )

    second_response = await client.post(
        "/api/v1/tarot/draw?spread_type=three_card",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_id = first_response.json()["reading_id"]
    second_id = second_response.json()["reading_id"]

    assert first_id != second_id

    user_result = await db_session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = user_result.scalar_one_or_none()

    assert user is not None

    readings_result = await db_session.execute(
        select(Reading).where(
            Reading.user_id == user.id,
            Reading.reading_type == "TAROT",
        )
    )

    readings = readings_result.scalars().all()

    assert len(readings) == 2