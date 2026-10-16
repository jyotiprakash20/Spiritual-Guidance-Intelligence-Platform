from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.relational import User, Profile
from app.schemas.profile import (
    UserFullProfileOut,
    ProfileUpdate,
    ProfileOut,
    UserPreferencesUpdate,
)

router = APIRouter()


# -------------------------------------------------------------------
# GET CURRENT USER PROFILE
# -------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserFullProfileOut,
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the authenticated user's complete profile.

    Profile is eagerly loaded with selectinload so that
    Pydantic serialization does not trigger an async lazy-load.
    """

    query = (
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == current_user.id)
    )

    result = await db.execute(query)
    user_record = result.scalar_one_or_none()

    if user_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user_record


# -------------------------------------------------------------------
# UPDATE PROFILE
# -------------------------------------------------------------------

@router.put(
    "/me/profile",
    response_model=ProfileOut,
)
async def update_my_profile(
    profile_in: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create or update the authenticated user's profile.
    """

    query = select(Profile).where(
        Profile.user_id == current_user.id
    )

    result = await db.execute(query)
    profile = result.scalar_one_or_none()

    # ---------------------------------------------------------------
    # Create profile if one does not exist
    # ---------------------------------------------------------------

    if profile is None:
        profile = Profile(
            user_id=current_user.id
        )
        db.add(profile)

    # ---------------------------------------------------------------
    # Apply only fields supplied by the client
    # ---------------------------------------------------------------

    update_data = profile_in.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(profile, field, value)

    # ---------------------------------------------------------------
    # Save changes safely
    # ---------------------------------------------------------------

    try:
        await db.commit()
        await db.refresh(profile)

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile could not be updated.",
        )

    return profile


# -------------------------------------------------------------------
# UPDATE USER PREFERENCES
# -------------------------------------------------------------------

@router.put(
    "/me/preferences",
    response_model=UserFullProfileOut,
)
async def update_my_preferences(
    prefs_in: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update preferences for the authenticated user.

    The user profile is eagerly loaded both before and after
    the update to prevent async lazy-loading during serialization.
    """

    query = (
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == current_user.id)
    )

    result = await db.execute(query)
    user_record = result.scalar_one_or_none()

    if user_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # ---------------------------------------------------------------
    # Update preferences
    # ---------------------------------------------------------------

    user_record.preferences = prefs_in.preferences

    try:
        await db.commit()

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User preferences could not be updated.",
        )

    # ---------------------------------------------------------------
    # Re-fetch with eager loading
    # ---------------------------------------------------------------

    result = await db.execute(query)
    updated_user = result.scalar_one_or_none()

    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found after update.",
        )

    return updated_user