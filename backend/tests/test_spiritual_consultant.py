
import pytest
from uuid import uuid4

from app.api.deps import get_current_user
from app.main import app
from app.models.relational import (
    Reading,
    SpiritualConsultantClient,
    User,
)
from app.schemas.user import UserRole


BASE_URL = "/api/v1/spiritual-consultant"


async def create_user(db_session, role, email=None):
    user = User(
        email=email or f"{uuid4().hex}@test.com",
        password_hash="test-password-hash",
        role=role,
    )
    db_session.add(user)
    await db_session.flush()
    return user


def authenticate_as(user):
    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user


@pytest.mark.asyncio
async def test_consultant_can_assign_and_list_client(client, db_session):
    consultant = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    seeker = await create_user(db_session, UserRole.USER.value)
    await db_session.commit()

    authenticate_as(consultant)

    response = await client.post(
        f"{BASE_URL}/clients",
        json={"client_id": str(seeker.id)},
    )

    assert response.status_code == 201
    assert response.json()["assignment"]["status"] == "ACTIVE"

    response = await client.get(f"{BASE_URL}/clients")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["clients"][0]["client_id"] == str(seeker.id)


@pytest.mark.asyncio
async def test_duplicate_active_assignment_returns_conflict(
    client, db_session
):
    consultant = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    seeker = await create_user(db_session, UserRole.USER.value)
    await db_session.commit()

    authenticate_as(consultant)

    first = await client.post(
        f"{BASE_URL}/clients",
        json={"client_id": str(seeker.id)},
    )
    second = await client.post(
        f"{BASE_URL}/clients",
        json={"client_id": str(seeker.id)},
    )

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_consultant_can_access_assigned_client_readings(
    client, db_session
):
    consultant = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    seeker = await create_user(db_session, UserRole.USER.value)

    db_session.add(
        SpiritualConsultantClient(
            consultant_id=consultant.id,
            client_id=seeker.id,
            status="ACTIVE",
        )
    )
    db_session.add_all([
        Reading(
            user_id=seeker.id,
            reading_type="TAROT",
            analysis_data={"source": "test"},
        ),
        Reading(
            user_id=seeker.id,
            reading_type="PALMISTRY",
            analysis_data={"source": "test"},
        ),
    ])
    await db_session.commit()

    authenticate_as(consultant)

    response = await client.get(
        f"{BASE_URL}/clients/{seeker.id}/readings"
    )

    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert {
        reading["reading_type"]
        for reading in response.json()["readings"]
    } == {"TAROT", "PALMISTRY"}


@pytest.mark.asyncio
async def test_inactive_assignment_blocks_reading_access(
    client, db_session
):
    consultant = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    seeker = await create_user(db_session, UserRole.USER.value)

    db_session.add(
        SpiritualConsultantClient(
            consultant_id=consultant.id,
            client_id=seeker.id,
            status="INACTIVE",
        )
    )
    await db_session.commit()

    authenticate_as(consultant)

    response = await client.get(
        f"{BASE_URL}/clients/{seeker.id}/readings"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_consultant_cannot_access_another_consultants_client(
    client, db_session
):
    consultant_one = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    consultant_two = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    seeker = await create_user(db_session, UserRole.USER.value)

    db_session.add(
        SpiritualConsultantClient(
            consultant_id=consultant_one.id,
            client_id=seeker.id,
            status="ACTIVE",
        )
    )
    await db_session.commit()

    authenticate_as(consultant_two)

    response = await client.get(
        f"{BASE_URL}/clients/{seeker.id}/readings"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [
        UserRole.USER.value,
        UserRole.TAROT_READER.value,
    ],
)
async def test_non_consultant_roles_are_forbidden(
    client, db_session, role
):
    user = await create_user(db_session, role)
    await db_session.commit()

    authenticate_as(user)

    response = await client.get(f"{BASE_URL}/clients")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_administrator_must_specify_consultant(
    client, db_session
):
    admin = await create_user(db_session, UserRole.ADMIN.value)
    await db_session.commit()

    authenticate_as(admin)

    response = await client.get(f"{BASE_URL}/clients")

    assert response.status_code == 400
    assert "consultant_id" in response.json()["detail"]


@pytest.mark.asyncio
async def test_administrator_can_assign_client_to_consultant(
    client, db_session
):
    admin = await create_user(db_session, UserRole.ADMIN.value)
    consultant = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    seeker = await create_user(db_session, UserRole.USER.value)
    await db_session.commit()

    authenticate_as(admin)

    response = await client.post(
        f"{BASE_URL}/clients",
        json={
            "consultant_id": str(consultant.id),
            "client_id": str(seeker.id),
        },
    )

    assert response.status_code == 201
    assignment = response.json()["assignment"]
    assert assignment["consultant_id"] == str(consultant.id)
    assert assignment["client_id"] == str(seeker.id)
    assert assignment["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_consultant_can_deactivate_assignment(
    client, db_session
):
    consultant = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    seeker = await create_user(db_session, UserRole.USER.value)

    db_session.add(
        SpiritualConsultantClient(
            consultant_id=consultant.id,
            client_id=seeker.id,
            status="ACTIVE",
        )
    )
    await db_session.commit()

    authenticate_as(consultant)

    response = await client.delete(
        f"{BASE_URL}/clients/{seeker.id}"
    )

    assert response.status_code == 200
    assert response.json()["assignment_status"] == "INACTIVE"

    readings_response = await client.get(
        f"{BASE_URL}/clients/{seeker.id}/readings"
    )
    assert readings_response.status_code == 404
