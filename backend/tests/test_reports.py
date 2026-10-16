import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.v1.endpoints.readings import router
from app.core.database import get_db
from app.models.relational import Profile, Reading, Report, User
from app.services.tarot_service import tarot_engine


# ============================================================
# TEST APPLICATION
# ============================================================

def create_test_app():
    """
    Create a small FastAPI application containing the real
    readings router.
    """

    app = FastAPI()

    app.include_router(
        router,
        prefix="/readings",
    )

    return app


# ============================================================
# TEST HELPERS
# ============================================================

async def create_user(
    db_session,
    email: str,
    role: str = "User",
):
    """
    Create a test user directly in the test database.
    """

    user = User(
        email=email,
        password_hash="test-password-hash",
        role=role,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


async def create_palm_reading(
    db_session,
    user_id,
):
    """
    Create a minimal valid palm reading that can be used
    as the source for composite synthesis.
    """

    palm_features = {
        "hand_type": {
            "type": "Water",
        },
        "palm_structure": {
            "length": 120.0,
            "width": 90.0,
        },
        "lines": {
            "life": {
                "status": "candidate_trajectory",
                "technical_confidence": 0.80,
            },
            "head": {
                "status": "candidate_trajectory",
                "technical_confidence": 0.75,
            },
            "heart": {
                "status": "candidate_trajectory",
                "technical_confidence": 0.78,
            },
        },
        "analysis_confidence": 0.80,
    }

    reading = Reading(
        user_id=user_id,
        reading_type="PALMISTRY",
        overall_insight_score=None,
        analysis_data=palm_features,
    )

    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    return reading


def get_valid_three_tarot_card_ids():
    """
    Get three valid Tarot IDs directly from the loaded catalog.

    This avoids hardcoding IDs and keeps the test compatible
    with the actual catalog used by the application.
    """

    catalog = getattr(tarot_engine, "catalog", None)

    if catalog is None:
        catalog = getattr(tarot_engine, "cards", None)

    if catalog is None:
        catalog = getattr(tarot_engine, "deck", None)

    assert catalog is not None
    assert isinstance(catalog, list)
    assert len(catalog) >= 3

    card_ids = []

    for card in catalog:
        if not isinstance(card, dict):
            continue

        card_id = card.get("id") or card.get("card_id")

        if card_id:
            card_ids.append(str(card_id))

        if len(card_ids) == 3:
            break

    assert len(card_ids) == 3

    return card_ids


async def request_composite(
    app,
    db_session,
    user,
    palm_reading_id,
    selected_card_ids,
):
    """
    Call the real composite-reading endpoint.
    """

    async def override_current_user():
        return user

    async def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )

    app.dependency_overrides[get_db] = override_db

    transport = ASGITransport(app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        response = await client.post(
            "/readings/composite-reading",
            data={
                "spread_type": "three_card",
                "palm_reading_id": str(palm_reading_id),
                "selected_card_ids": __import__("json").dumps(
                    selected_card_ids
                ),
            },
        )

    return response


def patch_intelligence_engines(monkeypatch):
    """
    Replace the intelligence/LLM layers with deterministic
    test responses.

    This keeps report tests independent of OpenRouter and
    external services.
    """

    async def not_async(*args, **kwargs):
        return None

    def mock_personality(*args, **kwargs):
        return {
            "status": "success",
            "engine": "test_personality_engine",
            "version": "TEST",
            "personality_profile": {
                "summary": "Test personality profile",
                "core_traits": [
                    "reflective",
                    "creative",
                ],
            },
            "alignment_score": 80.0,
            "analysis_confidence": 90.0,
        }

    def mock_recommendation(*args, **kwargs):
        return {
            "status": "success",
            "engine": "test_recommendation_engine",
            "version": "TEST",
            "top_themes": [
                {
                    "theme": "creativity",
                    "score": 75.0,
                }
            ],
            "recommendations": [
                {
                    "category": "Personal Development",
                    "title": "Test recommendation",
                    "description": "Test recommendation description",
                }
            ],
            "analysis_confidence": 90.0,
        }

    def mock_life_trends(*args, **kwargs):
        return {
            "status": "success",
            "engine": "test_life_trends_engine",
            "version": "TEST",
            "trend_summary": "Test life trend summary",
            "life_trends": [
                {
                    "area": "Personal Growth",
                    "theme": "Reflection",
                    "score": 70.0,
                }
            ],
            "opportunities": [
                {
                    "title": "Test opportunity",
                    "description": "Test opportunity description",
                }
            ],
            "analysis_confidence": 90.0,
        }

    def mock_synthesis(*args, **kwargs):
        return {
            "interpretation": (
                "This is a deterministic test interpretation."
            ),
            "synthesized_reading": (
                "This is a test synthesized reading."
            ),
            "key_themes": [
                "Reflection",
                "Creativity",
            ],
            "actionable_advice": [
                "Review your goals.",
                "Continue learning.",
            ],
            "personality_alignment": 80.0,
            "context_relevance": 75.0,
            "insight_score": 82.50,
            "overall_insight_score": 82.50,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.readings.personality_engine.analyze",
        mock_personality,
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.readings.recommendation_engine.generate",
        mock_recommendation,
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.readings.life_trends_engine.analyze",
        mock_life_trends,
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.readings.synthesis_engine.generate_composite_report",
        mock_synthesis,
    )


# ============================================================
# REPORT CREATION
# ============================================================

@pytest.mark.asyncio
async def test_composite_creates_report(
    db_session,
    monkeypatch,
):
    """
    A successful composite reading should create a Report
    record.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    user = await create_user(
        db_session,
        "report-create@test.com",
    )

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    selected_cards = get_valid_three_tarot_card_ids()

    response = await request_composite(
        app,
        db_session,
        user,
        palm_reading.id,
        selected_cards,
    )

    if response.status_code != 200:
        pytest.fail(
            "Composite report creation failed.\n"
            f"Status: {response.status_code}\n"
            f"Response: {response.text}"
        )

    data = response.json()

    assert data["status"] == "success"
    assert data["report_id"]
    assert data["reading_id"]

    report_result = await db_session.execute(
        select(Report).where(
            Report.id == data["report_id"]
        )
    )

    report = report_result.scalar_one_or_none()

    assert report is not None


# ============================================================
# REPORT -> READING RELATIONSHIP
# ============================================================

@pytest.mark.asyncio
async def test_report_is_linked_to_synthesized_reading(
    db_session,
    monkeypatch,
):
    """
    The Report should reference the SYNTHESIZED Reading
    created during composite processing.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    user = await create_user(
        db_session,
        "report-link@test.com",
    )

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    selected_cards = get_valid_three_tarot_card_ids()

    response = await request_composite(
        app,
        db_session,
        user,
        palm_reading.id,
        selected_cards,
    )

    assert response.status_code == 200

    data = response.json()

    report_result = await db_session.execute(
        select(Report).where(
            Report.id == data["report_id"]
        )
    )

    report = report_result.scalar_one()

    reading_result = await db_session.execute(
        select(Reading).where(
            Reading.id == data["reading_id"]
        )
    )

    reading = reading_result.scalar_one()

    assert report.reading_id == reading.id
    assert reading.reading_type == "SYNTHESIZED"
    assert report.user_id == user.id


# ============================================================
# REPORT USER OWNERSHIP
# ============================================================

@pytest.mark.asyncio
async def test_report_belongs_to_authenticated_user(
    db_session,
    monkeypatch,
):
    """
    The created Report must belong to the authenticated user.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    user = await create_user(
        db_session,
        "report-owner@test.com",
    )

    other_user = await create_user(
        db_session,
        "other-report-user@test.com",
    )

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    selected_cards = get_valid_three_tarot_card_ids()

    response = await request_composite(
        app,
        db_session,
        user,
        palm_reading.id,
        selected_cards,
    )

    assert response.status_code == 200

    data = response.json()

    report_result = await db_session.execute(
        select(Report).where(
            Report.id == data["report_id"]
        )
    )

    report = report_result.scalar_one()

    assert report.user_id == user.id
    assert report.user_id != other_user.id


# ============================================================
# REPORT CONTENT
# ============================================================

@pytest.mark.asyncio
async def test_report_stores_expected_content(
    db_session,
    monkeypatch,
):
    """
    The Report should persist the synthesized title,
    summary and actionable steps.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    user = await create_user(
        db_session,
        "report-content@test.com",
    )

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    selected_cards = get_valid_three_tarot_card_ids()

    response = await request_composite(
        app,
        db_session,
        user,
        palm_reading.id,
        selected_cards,
    )

    assert response.status_code == 200

    data = response.json()

    report_result = await db_session.execute(
        select(Report).where(
            Report.id == data["report_id"]
        )
    )

    report = report_result.scalar_one()

    assert (
        report.report_title
        == "Palmistry & Tarot Synthesis: Report Content"
    )

    assert (
        report.report_summary
        == "This is a test synthesized reading."
    )

    assert report.actionable_steps == [
        "Review your goals.",
        "Continue learning.",
    ]


# ============================================================
# READING CONTENT
# ============================================================

@pytest.mark.asyncio
async def test_synthesized_reading_contains_report_data(
    db_session,
    monkeypatch,
):
    """
    The synthesized Reading should retain the palm, Tarot,
    synthesis and M3 intelligence data.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    user = await create_user(
        db_session,
        "reading-data@test.com",
    )

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    selected_cards = get_valid_three_tarot_card_ids()

    response = await request_composite(
        app,
        db_session,
        user,
        palm_reading.id,
        selected_cards,
    )

    assert response.status_code == 200

    data = response.json()

    reading_result = await db_session.execute(
        select(Reading).where(
            Reading.id == data["reading_id"]
        )
    )

    reading = reading_result.scalar_one()

    assert reading.reading_type == "SYNTHESIZED"
    assert reading.overall_insight_score == 82.50

    analysis = reading.analysis_data

    assert "palm_features" in analysis
    assert "tarot" in analysis
    assert "synthesis" in analysis
    assert "personality_data" in analysis
    assert "recommendations" in analysis
    assert "life_trends" in analysis

    assert (
        analysis["selected_tarot_card_ids"]
        == selected_cards
    )


# ============================================================
# USER ISOLATION
# ============================================================

@pytest.mark.asyncio
async def test_user_cannot_use_another_users_palm_reading(
    db_session,
    monkeypatch,
):
    """
    A user must not be able to create a composite report
    using another user's palm reading.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    owner = await create_user(
        db_session,
        "palm-owner@test.com",
    )

    attacker = await create_user(
        db_session,
        "report-attacker@test.com",
    )

    palm_reading = await create_palm_reading(
        db_session,
        owner.id,
    )

    selected_cards = get_valid_three_tarot_card_ids()

    response = await request_composite(
        app,
        db_session,
        attacker,
        palm_reading.id,
        selected_cards,
    )

    assert response.status_code == 404

    assert (
        "Palm reading not found"
        in response.json()["detail"]
    )


# ============================================================
# INVALID READING ID
# ============================================================

@pytest.mark.asyncio
async def test_invalid_palm_reading_id_returns_400(
    db_session,
    monkeypatch,
):
    """
    An invalid UUID supplied as palm_reading_id should return
    HTTP 400.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    user = await create_user(
        db_session,
        "invalid-report-id@test.com",
    )

    selected_cards = get_valid_three_tarot_card_ids()

    response = await request_composite(
        app,
        db_session,
        user,
        "not-a-valid-uuid",
        selected_cards,
    )

    assert response.status_code == 400

    assert (
        "Invalid palm_reading_id"
        in response.json()["detail"]
    )


# ============================================================
# NO PALM DATA
# ============================================================

@pytest.mark.asyncio
async def test_report_generation_requires_palm_data(
    db_session,
    monkeypatch,
):
    """
    Composite report generation should fail when the user
    has no existing palm reading and does not upload an image.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    user = await create_user(
        db_session,
        "no-palm-report@test.com",
    )

    selected_cards = get_valid_three_tarot_card_ids()

    transport = ASGITransport(app)

    async def override_current_user():
        return user

    async def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        response = await client.post(
            "/readings/composite-reading",
            data={
                "spread_type": "three_card",
                "selected_card_ids": __import__("json").dumps(
                    selected_cards
                ),
            },
        )

    assert response.status_code == 404

    assert (
        "No palm reading is available"
        in response.json()["detail"]
    )


# ============================================================
# REPORT ID AND READING ID MATCH RESPONSE
# ============================================================

@pytest.mark.asyncio
async def test_response_ids_match_database_records(
    db_session,
    monkeypatch,
):
    """
    The report_id and reading_id returned by the API must
    correspond exactly to the records stored in PostgreSQL.
    """

    patch_intelligence_engines(monkeypatch)

    app = create_test_app()

    user = await create_user(
        db_session,
        "report-ids@test.com",
    )

    palm_reading = await create_palm_reading(
        db_session,
        user.id,
    )

    selected_cards = get_valid_three_tarot_card_ids()

    response = await request_composite(
        app,
        db_session,
        user,
        palm_reading.id,
        selected_cards,
    )

    assert response.status_code == 200

    data = response.json()

    report_result = await db_session.execute(
        select(Report).where(
            Report.id == data["report_id"]
        )
    )

    report = report_result.scalar_one_or_none()

    reading_result = await db_session.execute(
        select(Reading).where(
            Reading.id == data["reading_id"]
        )
    )

    reading = reading_result.scalar_one_or_none()

    assert report is not None
    assert reading is not None

    assert str(report.id) == data["report_id"]
    assert str(reading.id) == data["reading_id"]

    assert report.reading_id == reading.id
    assert report.user_id == user.id
    assert reading.user_id == user.id