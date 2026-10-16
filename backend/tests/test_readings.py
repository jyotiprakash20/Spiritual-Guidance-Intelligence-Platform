import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.relational import User, Profile, Reading, Report
from app.services.tarot_service import tarot_engine


# ===================================================================
# HELPERS
# ===================================================================


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


async def create_palm_reading(
    db_session,
    user_id,
):
    """
    Create a minimal stored Palmistry reading.

    This avoids running the actual CV pipeline in composite
    reading tests.
    """

    palm_features = {
        "hand_type": {
            "type": "Water",
            "element": "Water",
            "confidence": 0.85,
        },
        "palm_structure": {
            "is_palm_square": True,
            "is_finger_long": False,
        },
        "major_lines": {
            "life_line": {
                "status": "candidate_trajectory",
                "clarity": 0.75,
            },
            "head_line": {
                "status": "candidate_trajectory",
                "clarity": 0.72,
            },
            "heart_line": {
                "status": "candidate_trajectory",
                "clarity": 0.78,
            },
        },
        "mounts": {
            "Venus": {
                "strength": 0.70,
            }
        },
        "analysis_confidence": 0.80,
    }

    reading = Reading(
        user_id=user_id,
        reading_type="PALMISTRY",
        overall_insight_score=None,
        analysis_data={
            "features": palm_features,
        },
    )

    db_session.add(reading)

    await db_session.commit()
    await db_session.refresh(reading)

    return reading


# ===================================================================
# MOCK M3.2
# ===================================================================


def mock_personality_engine():
    return {
        "status": "success",
        "engine": "test_personality_engine",
        "version": "TEST",
        "alignment_score": 80.0,
        "analysis_confidence": 90.0,
        "personality_profile": {
            "summary": "Test personality profile",
            "core_traits": [
                "reflective",
                "creative",
            ],
        },
        "strengths": [
            "Creativity",
            "Reflection",
        ],
        "development_areas": [
            "Decision clarity",
        ],
    }


# ===================================================================
# MOCK M3.3
# ===================================================================


def mock_recommendation_engine():
    return {
        "status": "success",
        "engine": "test_recommendation_engine",
        "version": "TEST",
        "analysis_confidence": 90.0,
        "top_themes": [
            {
                "theme": "creativity",
                "score": 75.0,
            }
        ],
        "recommendations": [
            {
                "category": "Personal Development",
                "title": "Develop creative habits",
                "priority": "high",
            }
        ],
        "recommendations_by_category": {},
        "priority_recommendations": [],
        "recommendation_count": 1,
    }


# ===================================================================
# MOCK M3.4
# ===================================================================


def mock_life_trends_engine():
    return {
        "status": "success",
        "engine": "test_life_trends_engine",
        "version": "TEST",
        "analysis_confidence": 90.0,
        "trend_summary": "Test life trend summary",
        "life_trends": [
            {
                "area": "Personal Growth",
                "theme": "Reflection",
                "score": 75.0,
            }
        ],
        "opportunities": [
            {
                "title": "Explore a new learning opportunity",
            }
        ],
        "reflection_areas": [
            "Decision clarity",
        ],
        "trend_count": 1,
        "opportunity_count": 1,
    }


# ===================================================================
# MOCK M3.1
# ===================================================================


def mock_synthesis_engine():
    return {
        "synthesized_reading": (
            "This is a deterministic test composite reading."
        ),
        "interpretation": (
            "Test interpretation based on supplied "
            "palm and Tarot evidence."
        ),
        "key_themes": [
            "Reflection",
            "Growth",
        ],
        "personality_alignment": 80.0,
        "context_relevance": 75.0,
        "actionable_advice": [
            "Focus on personal development.",
            "Reflect before making major decisions.",
        ],
        "insight_score": 82.5,
        "overall_insight_score": 82.5,
    }


# ===================================================================
# TAROT TEST HELPER
# ===================================================================


def get_valid_three_tarot_card_ids():
    """
    Get three actual card IDs from the Tarot engine's loaded
    catalog.

    This is intentionally taken from the real Tarot service instead
    of hardcoding catalog IDs.

    That makes this test independent of the exact naming convention
    used by tarot_catalog.json.
    """

    catalog = getattr(
        tarot_engine,
        "catalog",
        None,
    )

    if catalog is None:
        catalog = getattr(
            tarot_engine,
            "cards",
            None,
        )

    if catalog is None:
        catalog = getattr(
            tarot_engine,
            "deck",
            None,
        )

    assert catalog is not None, (
        "Could not access the Tarot engine catalog. "
        "Check tarot_service.py."
    )

    assert isinstance(catalog, list), (
        "Tarot engine catalog must be a list."
    )

    assert len(catalog) >= 3, (
        "Tarot catalog must contain at least 3 cards."
    )

    card_ids = []

    for card in catalog:

        if not isinstance(card, dict):
            continue

        card_id = (
            card.get("id")
            or card.get("card_id")
        )

        if card_id:
            card_ids.append(str(card_id))

        if len(card_ids) == 3:
            break

    assert len(card_ids) == 3, (
        "Could not obtain three valid Tarot card IDs "
        "from the loaded Tarot catalog."
    )

    return card_ids


# ===================================================================
# 1. AUTHENTICATION
# ===================================================================


@pytest.mark.asyncio
async def test_composite_reading_requires_authentication(
    client: AsyncClient,
):
    response = await client.post(
        "/api/v1/readings/composite-reading",
        data={
            "spread_type": "three_card",
        },
    )

    assert response.status_code == 401


# ===================================================================
# 2. NO PALM DATA
# ===================================================================


@pytest.mark.asyncio
async def test_composite_reading_requires_palm_data(
    client: AsyncClient,
):
    token = await create_authenticated_user(
        client,
        "composite_no_palm@example.com",
    )

    response = await client.post(
        "/api/v1/readings/composite-reading",
        headers={
            "Authorization": f"Bearer {token}",
        },
        data={
            "spread_type": "three_card",
        },
    )

    assert response.status_code == 404

    data = response.json()

    assert "detail" in data

    assert (
        "No palm reading is available"
        in data["detail"]
    )


# ===================================================================
# 3. INVALID PALM UUID
# ===================================================================


@pytest.mark.asyncio
async def test_composite_reading_rejects_invalid_palm_reading_id(
    client: AsyncClient,
):
    token = await create_authenticated_user(
        client,
        "composite_invalid_uuid@example.com",
    )

    response = await client.post(
        "/api/v1/readings/composite-reading",
        headers={
            "Authorization": f"Bearer {token}",
        },
        data={
            "spread_type": "three_card",
            "palm_reading_id": "not-a-valid-uuid",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert "detail" in data

    assert "valid UUID" in data["detail"]


# ===================================================================
# 4. PALM READING OWNERSHIP
# ===================================================================


@pytest.mark.asyncio
async def test_composite_reading_rejects_other_users_palm_reading(
    client: AsyncClient,
    db_session,
):
    first_email = "composite_owner@example.com"

    await create_authenticated_user(
        client,
        first_email,
    )

    result = await db_session.execute(
        select(User).where(
            User.email == first_email
        )
    )

    first_user = result.scalar_one()

    palm_reading = await create_palm_reading(
        db_session,
        first_user.id,
    )

    second_email = "composite_attacker@example.com"

    second_token = await create_authenticated_user(
        client,
        second_email,
    )

    response = await client.post(
        "/api/v1/readings/composite-reading",
        headers={
            "Authorization": f"Bearer {second_token}",
        },
        data={
            "spread_type": "three_card",
            "palm_reading_id": str(
                palm_reading.id
            ),
        },
    )

    assert response.status_code == 404

    data = response.json()

    assert (
        "Palm reading not found"
        in data["detail"]
    )


# ===================================================================
# 5. INVALID SELECTED CARD JSON
# ===================================================================


@pytest.mark.asyncio
async def test_composite_reading_rejects_invalid_selected_card_json(
    client: AsyncClient,
    db_session,
):
    email = "composite_invalid_json@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    result = await db_session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one()

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    response = await client.post(
        "/api/v1/readings/composite-reading",
        headers={
            "Authorization": f"Bearer {token}",
        },
        data={
            "spread_type": "three_card",
            "palm_reading_id": str(
                palm_reading.id
            ),
            "selected_card_ids": "this-is-not-json",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert (
        "selected_card_ids must be a valid"
        in data["detail"]
    )


# ===================================================================
# 6. SELECTED CARDS MUST BE ARRAY
# ===================================================================


@pytest.mark.asyncio
async def test_composite_reading_rejects_non_array_selected_cards(
    client: AsyncClient,
    db_session,
):
    email = "composite_non_array@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    result = await db_session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one()

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    response = await client.post(
        "/api/v1/readings/composite-reading",
        headers={
            "Authorization": f"Bearer {token}",
        },
        data={
            "spread_type": "three_card",
            "palm_reading_id": str(
                palm_reading.id
            ),
            "selected_card_ids": json.dumps(
                {
                    "card": "something"
                }
            ),
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert (
        "selected_card_ids must be a JSON array"
        in data["detail"]
    )


# ===================================================================
# 7. SUCCESSFUL COMPOSITE READING
# ===================================================================


@pytest.mark.asyncio
async def test_composite_reading_success_with_selected_cards(
    client: AsyncClient,
    db_session,
    monkeypatch,
):
    """
    Full composite reading workflow.

    Uses:

    - Existing Palmistry reading
    - User-selected Tarot cards
    - M3.2 personality intelligence
    - M3.3 recommendation intelligence
    - M3.4 life trends intelligence
    - M3.1 synthesis

    External AI/network calls are mocked.
    """

    email = "composite_success@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    # ---------------------------------------------------------------
    # GET USER
    # ---------------------------------------------------------------

    result = await db_session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one()

    # ---------------------------------------------------------------
    # GET EXISTING PROFILE
    #
    # Signup already creates this profile.
    # DO NOT INSERT ANOTHER PROFILE.
    # ---------------------------------------------------------------

    profile_result = await db_session.execute(
        select(Profile).where(
            Profile.user_id == user.id
        )
    )

    profile = profile_result.scalar_one_or_none()

    assert profile is not None

    # ---------------------------------------------------------------
    # UPDATE EXISTING PROFILE
    # ---------------------------------------------------------------

    profile.full_name = "Composite Test User"
    profile.age_group = "21-30"
    profile.interests = "AI, Tarot, Technology"
    profile.spiritual_goals = "Personal growth"

    profile.dynamic_persona = {
        "theme": "reflective",
    }

    await db_session.commit()
    await db_session.refresh(profile)

    # ---------------------------------------------------------------
    # CREATE PALM READING
    # ---------------------------------------------------------------

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    # ---------------------------------------------------------------
    # MOCK M3.2
    # ---------------------------------------------------------------

    monkeypatch.setattr(
        "app.api.v1.endpoints.readings.personality_engine.analyze",
        lambda **kwargs: mock_personality_engine(),
    )

    # ---------------------------------------------------------------
    # MOCK M3.3
    # ---------------------------------------------------------------

    monkeypatch.setattr(
        "app.api.v1.endpoints.readings.recommendation_engine.generate",
        lambda **kwargs: mock_recommendation_engine(),
    )

    # ---------------------------------------------------------------
    # MOCK M3.4
    # ---------------------------------------------------------------

    monkeypatch.setattr(
        "app.api.v1.endpoints.readings.life_trends_engine.analyze",
        lambda **kwargs: mock_life_trends_engine(),
    )

    # ---------------------------------------------------------------
    # MOCK M3.1
    # ---------------------------------------------------------------

    monkeypatch.setattr(
        "app.api.v1.endpoints.readings.synthesis_engine.generate_composite_report",
        lambda **kwargs: mock_synthesis_engine(),
    )

    # ---------------------------------------------------------------
    # GET THREE REAL CARD IDS FROM THE LOADED CATALOG
    # ---------------------------------------------------------------

    selected_cards = (
        get_valid_three_tarot_card_ids()
    )

    assert len(selected_cards) == 3

    assert len(
        set(selected_cards)
    ) == 3

    # ---------------------------------------------------------------
    # SEND COMPOSITE REQUEST
    # ---------------------------------------------------------------

    response = await client.post(
        "/api/v1/readings/composite-reading",
        headers={
            "Authorization": f"Bearer {token}",
        },
        data={
            "spread_type": "three_card",
            "palm_reading_id": str(
                palm_reading.id
            ),
            "selected_card_ids": json.dumps(
                selected_cards
            ),
        },
    )

    # ---------------------------------------------------------------
    # DEBUG INFORMATION IF REQUEST FAILS
    #
    # This is useful because a 400 can come from Tarot validation.
    # ---------------------------------------------------------------

    if response.status_code != 200:
        pytest.fail(
            "Composite reading failed.\n"
            f"Status: {response.status_code}\n"
            f"Response: {response.text}\n"
            f"Selected cards: {selected_cards}"
        )

    assert response.status_code == 200

    data = response.json()

    # ---------------------------------------------------------------
    # BASIC RESPONSE
    # ---------------------------------------------------------------

    assert data["status"] == "success"

    assert "reading_id" in data
    assert "report_id" in data

    assert (
        data["palm_source"]
        == "existing_reading"
    )

    assert (
        data["spread_type"]
        == "three_card"
    )

    # ---------------------------------------------------------------
    # TAROT SELECTION
    # ---------------------------------------------------------------

    assert (
        data["tarot_selection_mode"]
        == "user_selected"
    )

    assert (
        data["selected_tarot_card_ids"]
        == selected_cards
    )

    # ---------------------------------------------------------------
    # M3.2
    # ---------------------------------------------------------------

    assert (
        data[
            "personality_intelligence"
        ]["status"]
        == "success"
    )

    # ---------------------------------------------------------------
    # M3.3
    # ---------------------------------------------------------------

    assert (
        data[
            "recommendation_intelligence"
        ]["status"]
        == "success"
    )

    # ---------------------------------------------------------------
    # M3.4
    # ---------------------------------------------------------------

    assert (
        data[
            "life_trends_intelligence"
        ]["status"]
        == "success"
    )

    # ---------------------------------------------------------------
    # SCORE
    # ---------------------------------------------------------------

    assert (
        data["overall_insight_score"]
        == 82.5
    )

    # ---------------------------------------------------------------
    # REPORT
    # ---------------------------------------------------------------

    assert isinstance(
        data["report"],
        dict,
    )

    assert (
        data["report"][
            "personality_intelligence"
        ]
        is not None
    )

    assert (
        data["report"][
            "recommendation_intelligence"
        ]
        is not None
    )

    assert (
        data["report"][
            "life_trends_intelligence"
        ]
        is not None
    )

    assert (
        data["report"][
            "intelligence"
        ]["personality"]
        is not None
    )

    # ---------------------------------------------------------------
    # DATABASE — SYNTHESIZED READING
    # ---------------------------------------------------------------

    reading_result = await db_session.execute(
        select(Reading).where(
            Reading.id
            == data["reading_id"]
        )
    )

    reading = (
        reading_result
        .scalar_one_or_none()
    )

    assert reading is not None

    assert reading.user_id == user.id

    assert (
        reading.reading_type
        == "SYNTHESIZED"
    )

    assert (
        float(
            reading.overall_insight_score
        )
        == 82.5
    )

    assert (
        reading.analysis_data
        is not None
    )

    assert (
        reading.analysis_data[
            "tarot_selection_mode"
        ]
        == "user_selected"
    )

    assert (
        reading.analysis_data[
            "selected_tarot_card_ids"
        ]
        == selected_cards
    )

    assert (
        reading.analysis_data[
            "personality_data"
        ]["status"]
        == "success"
    )

    assert (
        reading.analysis_data[
            "recommendations"
        ]["status"]
        == "success"
    )

    assert (
        reading.analysis_data[
            "life_trends"
        ]["status"]
        == "success"
    )

    # ---------------------------------------------------------------
    # DATABASE — REPORT
    # ---------------------------------------------------------------

    report_result = await db_session.execute(
        select(Report).where(
            Report.id
            == data["report_id"]
        )
    )

    report = (
        report_result
        .scalar_one_or_none()
    )

    assert report is not None

    assert report.user_id == user.id

    assert (
        report.reading_id
        == reading.id
    )

    assert (
        report.report_title
        == (
            "Palmistry & Tarot Synthesis: "
            "Composite Test User"
        )
    )

    assert (
        report.report_summary
        is not None
    )


# ===================================================================
# 8. DASHBOARD AUTHENTICATION
# ===================================================================


@pytest.mark.asyncio
async def test_dashboard_stats_requires_authentication(
    client: AsyncClient,
):
    response = await client.get(
        "/api/v1/readings/dashboard-stats"
    )

    assert response.status_code == 401


# ===================================================================
# 9. DASHBOARD STATS COUNTS
# ===================================================================


@pytest.mark.asyncio
async def test_dashboard_stats_counts_user_readings(
    client: AsyncClient,
    db_session,
):
    email = "dashboard_stats@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    result = await db_session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one()

    palm_reading = Reading(
        user_id=user.id,
        reading_type="PALMISTRY",
        overall_insight_score=None,
        analysis_data={
            "analysis_confidence": 0.85,
        },
    )

    tarot_reading = Reading(
        user_id=user.id,
        reading_type="TAROT",
        overall_insight_score=None,
        analysis_data={
            "spread_type": "three_card",
        },
    )

    synthesized_reading = Reading(
        user_id=user.id,
        reading_type="SYNTHESIZED",
        overall_insight_score=82.5,
        analysis_data={
            "synthesis": {},
        },
    )

    db_session.add_all(
        [
            palm_reading,
            tarot_reading,
            synthesized_reading,
        ]
    )

    await db_session.commit()

    response = await client.get(
        "/api/v1/readings/dashboard-stats",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"

    assert "stats" in data

    stats = data["stats"]

    assert (
        stats["palm_readings"]
        == 1
    )

    assert (
        stats["tarot_readings"]
        == 2
    )

    assert (
        stats["total_readings"]
        == 3
    )

    assert (
        stats["latest_confidence"]
        == 0.85
    )


# ===================================================================
# 10. DASHBOARD USER ISOLATION
# ===================================================================


@pytest.mark.asyncio
async def test_dashboard_stats_only_show_current_user_data(
    client: AsyncClient,
    db_session,
):
    first_email = "dashboard_first@example.com"
    second_email = "dashboard_second@example.com"

    first_token = await create_authenticated_user(
        client,
        first_email,
    )

    await create_authenticated_user(
        client,
        second_email,
    )

    first_result = await db_session.execute(
        select(User).where(
            User.email == first_email
        )
    )

    first_user = first_result.scalar_one()

    second_result = await db_session.execute(
        select(User).where(
            User.email == second_email
        )
    )

    second_user = second_result.scalar_one()

    first_reading = Reading(
        user_id=first_user.id,
        reading_type="PALMISTRY",
        analysis_data={
            "analysis_confidence": 0.90,
        },
    )

    second_palm = Reading(
        user_id=second_user.id,
        reading_type="PALMISTRY",
        analysis_data={
            "analysis_confidence": 0.50,
        },
    )

    second_tarot = Reading(
        user_id=second_user.id,
        reading_type="TAROT",
        analysis_data={},
    )

    db_session.add_all(
        [
            first_reading,
            second_palm,
            second_tarot,
        ]
    )

    await db_session.commit()

    response = await client.get(
        "/api/v1/readings/dashboard-stats",
        headers={
            "Authorization": f"Bearer {first_token}",
        },
    )

    assert response.status_code == 200

    stats = response.json()["stats"]

    assert (
        stats["palm_readings"]
        == 1
    )

    assert (
        stats["tarot_readings"]
        == 0
    )

    assert (
        stats["total_readings"]
        == 1
    )

    assert (
        stats["latest_confidence"]
        == 0.90
    )