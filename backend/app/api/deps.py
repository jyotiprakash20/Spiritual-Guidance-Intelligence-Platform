
from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.relational import User
from app.schemas.user import TokenPayload, UserRole


reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


PROFESSIONAL_ROLES = {
    UserRole.TAROT_READER.value,
    UserRole.SPIRITUAL_CONSULTANT.value,
}


def credentials_exception(
    detail: str = "Could not validate credentials",
) -> HTTPException:
    """
    Return the standard authentication failure response.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """
    Validate the JWT, retrieve the user, and enforce professional
    registration approval on every authenticated API request.
    """

    # ---------------------------------------------------------
    # Decode and validate JWT
    # ---------------------------------------------------------
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        token_data = TokenPayload(**payload)

        if not token_data.sub:
            raise credentials_exception()

        user_id = UUID(token_data.sub)

    except HTTPException:
        raise

    except (
        JWTError,
        ValidationError,
        ValueError,
        TypeError,
    ):
        raise credentials_exception()

    # ---------------------------------------------------------
    # Retrieve the current user from the database
    # ---------------------------------------------------------
    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception(
            detail="User not found",
        )

    # ---------------------------------------------------------
    # Enforce approval for professional accounts
    # ---------------------------------------------------------
    if user.role in PROFESSIONAL_ROLES:
        approval_status = (
            user.approval_status or ""
        ).upper()

        if approval_status != "APPROVED":
            if approval_status == "REJECTED":
                detail = (
                    "Your professional account has been rejected "
                    "or its approval has been revoked. "
                    "Please contact the administrator."
                )
            else:
                detail = (
                    "Your professional registration is awaiting "
                    "administrator approval."
                )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )

    return user


def require_roles(
    allowed_roles: List[UserRole],
):
    """
    Validate that the current user has one of the allowed roles.

    Administrators retain their existing role-based access.
    Professional accounts must also pass the approval check in
    get_current_user() before reaching this dependency.
    """

    allowed_values = {
        role.value
        for role in allowed_roles
    }

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:

        # -----------------------------------------------------
        # Administrator access
        # -----------------------------------------------------
        if current_user.role == UserRole.ADMIN.value:
            return current_user

        # -----------------------------------------------------
        # Role validation
        # -----------------------------------------------------
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Access forbidden: requires one of the "
                    f"following roles: {sorted(allowed_values)}"
                ),
            )

        return current_user

    return role_checker
