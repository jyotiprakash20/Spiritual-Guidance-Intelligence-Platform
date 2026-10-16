from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.user import UserRole

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.relational import Profile, User
from app.schemas.user import Token, UserCreate, UserOut


router = APIRouter()


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user.

    New registrations always receive the normal User role.
    Privileged roles must be assigned through an authorized
    administrative workflow.
    """

    # ---------------------------------------------------------
    # Normalize input
    # ---------------------------------------------------------

    email = user_in.email.strip().lower()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required.",
        )

    if not user_in.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required.",
        )

    # ---------------------------------------------------------
    # Check whether the email already exists
    # ---------------------------------------------------------

    result = await db.execute(
        select(User).where(User.email == email)
    )

    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    # ---------------------------------------------------------
    # Create user
    # ---------------------------------------------------------


    requested_role = user_in.role

    # Never allow public signup as an administrator.
    if requested_role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator accounts cannot be created through public signup.",
        )

    # Only Tarot Readers and Spiritual Consultants need approval.
    is_professional = requested_role in {
        UserRole.TAROT_READER,
        UserRole.SPIRITUAL_CONSULTANT,
    }

    new_user = User(
        email=email,
        password_hash=get_password_hash(user_in.password),
        role=requested_role.value,
        approval_status="PENDING" if is_professional else "APPROVED",
    )

    db.add(new_user)


    try:
        # Flush first so new_user.id is available for Profile.
        await db.flush()

        # -----------------------------------------------------
        # Create associated profile
        # -----------------------------------------------------

        new_profile = Profile(
            user_id=new_user.id,
        )

        db.add(new_profile)

        # -----------------------------------------------------
        # Commit transaction
        # -----------------------------------------------------

        await db.commit()

        # Refresh the user so response_model receives
        # the persisted database values.
        await db.refresh(new_user)

    except IntegrityError:
        await db.rollback()

        # This can happen if another request creates the same
        # email between our initial SELECT and the INSERT.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User registration failed. Please try again.",
        )

    return new_user


@router.post(
    "/login",
    response_model=Token,
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate a user and return a JWT access token.

    OAuth2PasswordRequestForm uses:

        username -> user's email
        password -> user's password
    """

    # ---------------------------------------------------------
    # Normalize login email
    # ---------------------------------------------------------

    email = form_data.username.strip().lower()

    if not email or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ---------------------------------------------------------
    # Find user
    # ---------------------------------------------------------

    result = await db.execute(
        select(User).where(User.email == email)
    )

    user = result.scalar_one_or_none()

    # ---------------------------------------------------------
    # Verify credentials
    # ---------------------------------------------------------

    if user is None or not verify_password(
        form_data.password,
        user.password_hash,
    ):
        # Keep the same response for:
        # - unknown email
        # - incorrect password
        #
        # This prevents user enumeration.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    
    if (
        user.role in {
            UserRole.TAROT_READER.value,
            UserRole.SPIRITUAL_CONSULTANT.value,
        }
        and user.approval_status != "APPROVED"
    ):
        if user.approval_status == "REJECTED":
            detail = (
                "Your registration was rejected. "
                "Please contact the administrator."
            )
        else:
            detail = (
                "Your registration is awaiting administrator approval."
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


    # ---------------------------------------------------------
    # Generate JWT
    # ---------------------------------------------------------

    access_token = create_access_token(
        subject=user.id,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }