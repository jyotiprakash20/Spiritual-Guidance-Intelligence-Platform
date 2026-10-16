
import pytest
from uuid import uuid4

from app.api.deps import get_current_user
from app.main import app
from app.models.relational import User, Reading
from app.schemas.user import UserRole


BASE_URL = "/api/v1/tarot-reader"


async def create_user(db_session, role, email=None):
    """Create a test user in the isolated test database."""
    user = User(
        email=email or f"{uuid4().hex}@test.com",
        password_hash="test-password-hash",
        role=role,
    )
    db_session.add(user)
    await db_session.flush()
    return user


def authenticate_as(user):
    """Override authentication for a specific test user."""

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )


@pytest.mark.asyncio
async def test_reader_can_assign_and_list_client(
    client, db_session
):
    reader = await create_user(
        db_session, UserRole.TAROT_READER.value
    )
    seeker = await create_user(
        db_session, UserRole.USER.value
    )
    await db_session.commit()

    authenticate_as(reader)

    response = await client.post(
        f"{BASE_URL}/clients",
        json={"client_id": str(seeker.id)},
    )

    assert response.status_code == 201
    assert response.json()["assignment"]["status"] == "ACTIVE"

    response = await client.get(
        f"{BASE_URL}/clients"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["clients"][0]["client_id"] == str(seeker.id)


@pytest.mark.asyncio
async def test_duplicate_active_assignment_returns_conflict(
    client, db_session
):
    reader = await create_user(
        db_session, UserRole.TAROT_READER.value
    )
    seeker = await create_user(
        db_session, UserRole.USER.value
    )
    await db_session.commit()

    authenticate_as(reader)

    first = await client.post(
        f"{BASE_URL}/clients",
        json={"client_id": str(seeker.id)},
    )
    assert first.status_code == 201

    second = await client.post(
        f"{BASE_URL}/clients",
        json={"client_id": str(seeker.id)},
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_reader_can_access_assigned_client_readings(
    client, db_session
):
    reader = await create_user(
        db_session, UserRole.TAROT_READER.value
    )
    seeker = await create_user(
        db_session, UserRole.USER.value
    )

    db_session.add(
        Reading(
            user_id=seeker.id,
            reading_type="TAROT",
            analysis_data={"test": True},
        )
    )
    db_session.add(
        Reading(
            user_id=seeker.id,
            reading_type="PALMISTRY",
            analysis_data={"test": True},
        )
    )
    await db_session.flush()

    from app.models.relational import TarotReaderClient

    db_session.add(
        TarotReaderClient(
            reader_id=reader.id,
            client_id=seeker.id,
            status="ACTIVE",
        )
    )
    await db_session.commit()

    authenticate_as(reader)

    response = await client.get(
        f"{BASE_URL}/clients/{seeker.id}/readings"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert {
        item["reading_type"] for item in data["readings"]
    } == {"TAROT", "PALMISTRY"}


@pytest.mark.asyncio
async def test_inactive_assignment_blocks_reading_access(
    client, db_session
):
    reader = await create_user(
        db_session, UserRole.TAROT_READER.value
    )
    seeker = await create_user(
        db_session, UserRole.USER.value
    )

    from app.models.relational import TarotReaderClient

    db_session.add(
        TarotReaderClient(
            reader_id=reader.id,
            client_id=seeker.id,
            status="INACTIVE",
        )
    )
    await db_session.commit()

    authenticate_as(reader)

    response = await client.get(
        f"{BASE_URL}/clients/{seeker.id}/readings"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reader_cannot_access_another_readers_active_client(
    client, db_session
):
    reader_one = await create_user(
        db_session, UserRole.TAROT_READER.value
    )
    reader_two = await create_user(
        db_session, UserRole.TAROT_READER.value
    )
    seeker = await create_user(
        db_session, UserRole.USER.value
    )

    from app.models.relational import TarotReaderClient

    db_session.add(
        TarotReaderClient(
            reader_id=reader_one.id,
            client_id=seeker.id,
            status="ACTIVE",
        )
    )
    await db_session.commit()

    authenticate_as(reader_two)

    response = await client.get(
        f"{BASE_URL}/clients/{seeker.id}/readings"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [
        UserRole.USER.value,
        UserRole.SPIRITUAL_CONSULTANT.value,
    ],
)
async def test_non_reader_roles_are_forbidden(
    client, db_session, role
):
    user = await create_user(db_session, role)
    await db_session.commit()

    authenticate_as(user)

    response = await client.get(
        f"{BASE_URL}/clients"
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_administrator_must_specify_reader(
    client, db_session
):
    admin = await create_user(
        db_session, UserRole.ADMIN.value
    )
    await db_session.commit()

    authenticate_as(admin)

    response = await client.get(
        f"{BASE_URL}/clients"
    )

    assert response.status_code == 400
    assert "reader_id" in response.json()["detail"]


@pytest.mark.asyncio
async def test_administrator_can_assign_client_to_reader(
    client, db_session
):
    admin = await create_user(
        db_session, UserRole.ADMIN.value
    )
    reader = await create_user(
        db_session, UserRole.TAROT_READER.value
    )
    seeker = await create_user(
        db_session, UserRole.USER.value
    )
    await db_session.commit()

    authenticate_as(admin)

    response = await client.post(
        f"{BASE_URL}/clients",
        json={
            "reader_id": str(reader.id),
            "client_id": str(seeker.id),
        },
    )

    assert response.status_code == 201
    assignment = response.json()["assignment"]
    assert assignment["reader_id"] == str(reader.id)
    assert assignment["client_id"] == str(seeker.id)
    assert assignment["status"] == "ACTIVE"
