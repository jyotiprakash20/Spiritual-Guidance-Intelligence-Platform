
import pytest
from uuid import uuid4

from app.api.deps import get_current_user
from app.main import app
from app.models.relational import (
    ConsultationNote,
    SpiritualConsultantClient,
    User,
)
from app.schemas.user import UserRole


BASE_URL = "/api/v1/consultation-notes"


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


async def create_note(db_session, consultant, client_user):
    note = ConsultationNote(
        consultant_id=consultant.id,
        client_id=client_user.id,
        title="Test Consultation",
        session_notes="Private test notes.",
        follow_up_actions=["Schedule follow-up"],
        progress_status="IN_PROGRESS",
    )
    db_session.add(note)
    await db_session.flush()
    return note


@pytest.mark.asyncio
async def test_consultant_cannot_get_another_consultants_note(
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
    note = await create_note(db_session, consultant_one, seeker)
    await db_session.commit()

    authenticate_as(consultant_two)

    response = await client.get(f"{BASE_URL}/{note.id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_consultant_cannot_list_another_consultants_notes(
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
    note = await create_note(db_session, consultant_one, seeker)
    await db_session.commit()

    authenticate_as(consultant_two)

    response = await client.get(BASE_URL)

    assert response.status_code == 200
    result = response.json()
    assert result["count"] == 0
    assert all(
        item["id"] != str(note.id)
        for item in result["notes"]
    )


@pytest.mark.asyncio
async def test_deactivated_assignment_blocks_note_access(
    client, db_session
):
    consultant = await create_user(
        db_session, UserRole.SPIRITUAL_CONSULTANT.value
    )
    seeker = await create_user(db_session, UserRole.USER.value)

    assignment = SpiritualConsultantClient(
        consultant_id=consultant.id,
        client_id=seeker.id,
        status="ACTIVE",
    )
    db_session.add(assignment)

    note = await create_note(db_session, consultant, seeker)
    await db_session.commit()

    # Simulate the client assignment being deactivated.
    assignment.status = "INACTIVE"
    await db_session.commit()

    authenticate_as(consultant)

    response = await client.get(f"{BASE_URL}/{note.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No active assignment exists for this client."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [
        UserRole.USER.value,
        UserRole.TAROT_READER.value,
    ],
)
async def test_unauthorized_roles_cannot_manage_consultation_notes(
    client, db_session, role
):
    user = await create_user(db_session, role)
    await db_session.commit()

    authenticate_as(user)

    response = await client.get(BASE_URL)

    assert response.status_code == 403



@pytest.mark.asyncio
async def test_consultant_cannot_update_another_consultants_note(
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
    note = await create_note(db_session, consultant_one, seeker)
    await db_session.commit()

    authenticate_as(consultant_two)

    response = await client.patch(
        f"{BASE_URL}/{note.id}",
        json={"title": "Unauthorized change"},
    )

    assert response.status_code == 404

    # Verify the original note was not changed.
    await db_session.refresh(note)
    assert note.title == "Test Consultation"


@pytest.mark.asyncio
async def test_consultant_cannot_delete_another_consultants_note(
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
    note = await create_note(db_session, consultant_one, seeker)
    note_id = note.id
    await db_session.commit()

    authenticate_as(consultant_two)

    response = await client.delete(f"{BASE_URL}/{note_id}")

    assert response.status_code == 404

    # Verify the note still exists.
    result = await db_session.get(ConsultationNote, note_id)
    assert result is not None


@pytest.mark.asyncio
async def test_administrator_can_list_consultant_notes(
    client, db_session
):
    admin = await create_user(db_session, UserRole.ADMIN.value)
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
    note = await create_note(db_session, consultant, seeker)
    await db_session.commit()

    authenticate_as(admin)

    response = await client.get(
        BASE_URL,
        params={"consultant_id": str(consultant.id)},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["count"] == 1
    assert result["notes"][0]["id"] == str(note.id)


@pytest.mark.asyncio
async def test_administrator_cannot_create_consultation_note(
    client, db_session
):
    admin = await create_user(db_session, UserRole.ADMIN.value)
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

    authenticate_as(admin)

    response = await client.post(
        BASE_URL,
        params={"consultant_id": str(consultant.id)},
        json={
            "client_id": str(seeker.id),
            "title": "Admin-created note",
            "session_notes": "This should be rejected.",
            "follow_up_actions": [],
            "progress_status": "IN_PROGRESS",
        },
    )

    assert response.status_code == 403

@pytest.mark.asyncio
async def test_administrator_can_retrieve_consultant_note(
    client, db_session
):
    admin = await create_user(db_session, UserRole.ADMIN.value)
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
    note = await create_note(db_session, consultant, seeker)
    await db_session.commit()

    authenticate_as(admin)

    response = await client.get(
        f"{BASE_URL}/{note.id}",
        params={"consultant_id": str(consultant.id)},
    )

    assert response.status_code == 200
    assert response.json()["note"]["id"] == str(note.id)


@pytest.mark.asyncio
async def test_administrator_cannot_update_consultant_note(
    client, db_session
):
    admin = await create_user(db_session, UserRole.ADMIN.value)
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
    note = await create_note(db_session, consultant, seeker)
    await db_session.commit()

    authenticate_as(admin)

    response = await client.patch(
        f"{BASE_URL}/{note.id}",
        params={"consultant_id": str(consultant.id)},
        json={"title": "Unauthorized update"},
    )

    assert response.status_code == 403

    await db_session.refresh(note)
    assert note.title == "Test Consultation"


@pytest.mark.asyncio
async def test_administrator_cannot_delete_consultant_note(
    client, db_session
):
    admin = await create_user(db_session, UserRole.ADMIN.value)
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
    note = await create_note(db_session, consultant, seeker)
    note_id = note.id
    await db_session.commit()

    authenticate_as(admin)

    response = await client.delete(
        f"{BASE_URL}/{note_id}",
        params={"consultant_id": str(consultant.id)},
    )

    assert response.status_code == 403

    result = await db_session.get(ConsultationNote, note_id)
    assert result is not None
