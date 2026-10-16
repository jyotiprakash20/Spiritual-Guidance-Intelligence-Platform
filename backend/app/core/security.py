from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import jwt

from app.core.config import settings


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify a plain-text password against a bcrypt password hash.

    Returns False instead of exposing bcrypt errors for malformed
    or invalid password hashes.
    """

    if not isinstance(plain_password, str):
        return False

    if not isinstance(hashed_password, str):
        return False

    if not plain_password or not hashed_password:
        return False

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )

    except (ValueError, TypeError):
        return False


def get_password_hash(
    password: str,
) -> str:
    """
    Generate a bcrypt password hash.
    """

    if not isinstance(password, str):
        raise TypeError(
            "Password must be a string."
        )

    if not password:
        raise ValueError(
            "Password cannot be empty."
        )

    salt = bcrypt.gensalt()

    return bcrypt.hashpw(
        password.encode("utf-8"),
        salt,
    ).decode("utf-8")


def create_access_token(
    subject: Any,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    The subject is stored as a string in the JWT `sub` claim.

    If expires_delta is provided, it determines the token
    lifetime. Otherwise, the configured application lifetime
    is used.
    """

    if subject is None:
        raise ValueError(
            "Token subject cannot be None."
        )

    if expires_delta is not None:
        if expires_delta.total_seconds() <= 0:
            raise ValueError(
                "Token expiration duration must be positive."
            )

        expire = (
            datetime.now(timezone.utc)
            + expires_delta
        )

    else:
        if settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise ValueError(
                "ACCESS_TOKEN_EXPIRE_MINUTES must be positive."
            )

        expire = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        )

    payload = {
        "sub": str(subject),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )