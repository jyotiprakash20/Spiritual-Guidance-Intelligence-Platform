import io

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from app.models.relational import Reading, User


# -------------------------------------------------------------------
# HELPER: CREATE TEST USER AND GET JWT
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
# HELPER: CREATE A VALID IMAGE FILE
# -------------------------------------------------------------------

def create_test_image() -> bytes:
    """
    Create a small valid PNG image in memory.

    This is used only to verify that the API accepts
    an actual image file. It is NOT expected to contain
    a detectable palm.
    """

    image = Image.new(
        "RGB",
        (256, 256),
        color="white",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


# -------------------------------------------------------------------
# UNAUTHENTICATED REQUEST
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_palm_analysis_requires_authentication(
    client: AsyncClient,
):
    """
    Palm analysis must reject requests without a JWT.
    """

    image_bytes = create_test_image()

    response = await client.post(
        "/api/v1/palm/analyze",
        files={
            "file": (
                "test.png",
                image_bytes,
                "image/png",
            )
        },
    )

    assert response.status_code == 401


# -------------------------------------------------------------------
# INVALID FILE TYPE
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_palm_analysis_rejects_non_image_file(
    client: AsyncClient,
):
    """
    Non-image uploads must be rejected before
    entering the palm-analysis engine.
    """

    token = await create_authenticated_user(
        client,
        "palm_invalid_file@example.com",
    )

    response = await client.post(
        "/api/v1/palm/analyze",
        headers={
            "Authorization": f"Bearer {token}",
        },
        files={
            "file": (
                "test.txt",
                b"This is not an image.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Uploaded file must be an image."
    )


# -------------------------------------------------------------------
# EMPTY IMAGE
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_palm_analysis_rejects_empty_file(
    client: AsyncClient,
):
    """
    Empty uploads must be rejected.
    """

    token = await create_authenticated_user(
        client,
        "palm_empty_file@example.com",
    )

    response = await client.post(
        "/api/v1/palm/analyze",
        headers={
            "Authorization": f"Bearer {token}",
        },
        files={
            "file": (
                "empty.png",
                b"",
                "image/png",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Uploaded image is empty."
    )


# -------------------------------------------------------------------
# VALID IMAGE UPLOAD
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_palm_analysis_accepts_image_upload(
    client: AsyncClient,
):
    """
    Verify that a syntactically valid image reaches
    the palm-analysis pipeline.

    A blank image is intentionally used here, so a
    422 'palm not detected' response is valid.
    """

    token = await create_authenticated_user(
        client,
        "palm_valid_image@example.com",
    )

    image_bytes = create_test_image()

    response = await client.post(
        "/api/v1/palm/analyze",
        headers={
            "Authorization": f"Bearer {token}",
        },
        files={
            "file": (
                "test.png",
                image_bytes,
                "image/png",
            )
        },
    )

    # A valid image should reach the palm engine.
    #
    # Since this is a blank image and contains no palm,
    # the expected application-level result is 422.
    assert response.status_code == 422

    data = response.json()

    assert "detail" in data


# -------------------------------------------------------------------
# INVALID IMAGE CONTENT WITH IMAGE MIME TYPE
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_palm_analysis_handles_invalid_image_content(
    client: AsyncClient,
):
    """
    The MIME type may say image/png while the actual
    bytes are not an image.

    The endpoint should handle this safely.
    """

    token = await create_authenticated_user(
        client,
        "palm_corrupt_image@example.com",
    )

    response = await client.post(
        "/api/v1/palm/analyze",
        headers={
            "Authorization": f"Bearer {token}",
        },
        files={
            "file": (
                "corrupt.png",
                b"this is definitely not a real png file",
                "image/png",
            )
        },
    )

    # Depending on the palm engine's image decoder,
    # this should normally become a controlled 400 or 500.
    assert response.status_code in {400, 500}

    data = response.json()

    assert "detail" in data


# -------------------------------------------------------------------
# DATABASE SHOULD NOT CONTAIN A READING AFTER FAILED ANALYSIS
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_palm_analysis_does_not_create_reading(
    client: AsyncClient,
    db_session,
):
    """
    A failed palm analysis should not create a PALMISTRY
    reading in the database.
    """

    email = "palm_failed_db@example.com"

    token = await create_authenticated_user(
        client,
        email,
    )

    image_bytes = create_test_image()

    response = await client.post(
        "/api/v1/palm/analyze",
        headers={
            "Authorization": f"Bearer {token}",
        },
        files={
            "file": (
                "blank.png",
                image_bytes,
                "image/png",
            )
        },
    )

    assert response.status_code == 422

    user_result = await db_session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = user_result.scalar_one_or_none()

    assert user is not None

    reading_result = await db_session.execute(
        select(Reading).where(
            Reading.user_id == user.id,
            Reading.reading_type == "PALMISTRY",
        )
    )

    reading = reading_result.scalar_one_or_none()

    assert reading is None