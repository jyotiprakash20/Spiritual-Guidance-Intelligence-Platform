
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_roles
from app.models.relational import (
    AdminActivityLog,
    Reading,
    User,
)
from app.schemas.user import UserRole

router = APIRouter()


# ---------------------------------------------------------
# Request schemas
# ---------------------------------------------------------
class UserRoleUpdate(BaseModel):
    role: UserRole


class UserApprovalUpdate(BaseModel):
    approval_status: str = Field(
        ...,
        pattern="^(APPROVED|REJECTED)$",
    )


# ---------------------------------------------------------
# Admin overview statistics
# ---------------------------------------------------------
@router.get("/stats")
async def get_admin_stats(
    current_user: User = Depends(
        require_roles([UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    total_users_result = await db.execute(
        select(func.count()).select_from(User)
    )

    total_readings_result = await db.execute(
        select(func.count()).select_from(Reading)
    )

    role_result = await db.execute(
        select(User.role, func.count(User.id))
        .group_by(User.role)
    )

    reading_type_result = await db.execute(
        select(Reading.reading_type, func.count(Reading.id))
        .group_by(Reading.reading_type)
    )

    return {
        "total_users": total_users_result.scalar_one(),
        "total_readings": total_readings_result.scalar_one(),
        "users_by_role": {
            role: count
            for role, count in role_result.all()
        },
        "readings_by_type": {
            reading_type: count
            for reading_type, count in reading_type_result.all()
        },
    }


# ---------------------------------------------------------
# User management: list users
# ---------------------------------------------------------
@router.get("/users")
async def get_admin_users(
    search: str | None = Query(
        default=None,
        max_length=255,
    ),
    role: str | None = Query(
        default=None,
        max_length=50,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_user: User = Depends(
        require_roles([UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    statement = select(
        User.id,
        User.email,
        User.role,
        User.approval_status,
        User.created_at,
    )

    if search:
        statement = statement.where(
            User.email.ilike(f"%{search.strip()}%")
        )

    if role:
        statement = statement.where(
            User.role == role
        )

    statement = (
        statement
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(statement)
    users = result.mappings().all()

    return {
        "count": len(users),
        "limit": limit,
        "offset": offset,
        "users": [
            {
                "id": str(user["id"]),
                "email": user["email"],
                "role": user["role"],
                "approval_status": user["approval_status"],
                "created_at": (
                    user["created_at"].isoformat()
                    if user["created_at"]
                    else None
                ),
            }
            for user in users
        ],
    }


# ---------------------------------------------------------
# Professional registrations awaiting approval
# ---------------------------------------------------------
@router.get("/pending-registrations")
async def get_pending_registrations(
    current_user: User = Depends(
        require_roles([UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    professional_roles = [
        UserRole.TAROT_READER.value,
        UserRole.SPIRITUAL_CONSULTANT.value,
    ]

    result = await db.execute(
        select(User)
        .where(
            User.role.in_(professional_roles),
            User.approval_status == "PENDING",
        )
        .order_by(User.created_at.asc())
    )

    users = result.scalars().all()

    return {
        "count": len(users),
        "registrations": [
            {
                "id": str(user.id),
                "email": user.email,
                "role": user.role,
                "approval_status": user.approval_status,
                "created_at": (
                    user.created_at.isoformat()
                    if user.created_at
                    else None
                ),
            }
            for user in users
        ],
    }


# ---------------------------------------------------------
# Approve or reject professional registrations
# ---------------------------------------------------------
@router.patch("/users/{user_id}/approval")
async def update_user_approval(
    user_id: UUID,
    payload: UserApprovalUpdate,
    current_user: User = Depends(
        require_roles([UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    target_user = result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    professional_roles = {
        UserRole.TAROT_READER.value,
        UserRole.SPIRITUAL_CONSULTANT.value,
    }

    if target_user.role not in professional_roles:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only Tarot Reader and Spiritual Consultant "
                "accounts require approval."
            ),
        )

    old_status = target_user.approval_status
    new_status = payload.approval_status

    if old_status == new_status:
        return {
            "message": (
                f"Registration is already {new_status.lower()}."
            ),
            "user": {
                "id": str(target_user.id),
                "email": target_user.email,
                "role": target_user.role,
                "approval_status": target_user.approval_status,
            },
        }

    target_user.approval_status = new_status

    activity = AdminActivityLog(
        admin_id=current_user.id,
        action="REGISTRATION_APPROVAL_UPDATED",
        target_user_id=target_user.id,
        old_value=old_status,
        new_value=new_status,
        details={
            "target_email": target_user.email,
            "target_role": target_user.role,
        },
    )

    db.add(activity)

    try:
        # Save the status change and activity log together.
        await db.commit()
        await db.refresh(target_user)

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update registration approval.",
        )

    return {
        "message": (
            f"Registration {new_status.lower()} successfully."
        ),
        "user": {
            "id": str(target_user.id),
            "email": target_user.email,
            "role": target_user.role,
            "approval_status": target_user.approval_status,
        },
    }


# ---------------------------------------------------------
# User management: update role and record activity
# ---------------------------------------------------------
@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    current_user: User = Depends(
        require_roles([UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    target_user = result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    new_role = payload.role.value
    old_role = target_user.role

    # Prevent an administrator from demoting themselves.
    if (
        target_user.id == current_user.id
        and new_role != UserRole.ADMIN.value
    ):
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own administrator role",
        )

    # Prevent demoting the last administrator.
    if (
        old_role == UserRole.ADMIN.value
        and new_role != UserRole.ADMIN.value
    ):
        admin_count_result = await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN.value)
        )

        admin_count = admin_count_result.scalar_one()

        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The platform must have at least one administrator"
                ),
            )

    # Avoid creating duplicate logs for unchanged roles.
    if old_role == new_role:
        return {
            "message": "User already has this role",
            "user": {
                "id": str(target_user.id),
                "email": target_user.email,
                "role": target_user.role,
            },
        }

    target_user.role = new_role

    activity = AdminActivityLog(
        admin_id=current_user.id,
        action="ROLE_UPDATED",
        target_user_id=target_user.id,
        old_value=old_role,
        new_value=new_role,
        details={
            "target_email": target_user.email,
        },
    )

    db.add(activity)

    try:
        # Save the role change and activity log together.
        await db.commit()
        await db.refresh(target_user)

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update user role and activity log",
        )

    return {
        "message": "User role updated successfully",
        "user": {
            "id": str(target_user.id),
            "email": target_user.email,
            "role": target_user.role,
        },
    }


# ---------------------------------------------------------
# Admin activity log: list recent administrative actions
# ---------------------------------------------------------
@router.get("/activity-logs")
async def get_admin_activity_logs(
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_user: User = Depends(
        require_roles([UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    statement = (
        select(AdminActivityLog, User.email)
        .outerjoin(
            User,
            AdminActivityLog.admin_id == User.id,
        )
        .order_by(AdminActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(statement)
    rows = result.all()

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "activity_logs": [
            {
                "id": str(log.id),
                "admin_id": (
                    str(log.admin_id)
                    if log.admin_id
                    else None
                ),
                "admin_email": admin_email,
                "action": log.action,
                "target_user_id": (
                    str(log.target_user_id)
                    if log.target_user_id
                    else None
                ),
                "old_value": log.old_value,
                "new_value": log.new_value,
                "details": log.details,
                "created_at": (
                    log.created_at.isoformat()
                    if log.created_at
                    else None
                ),
            }
            for log, admin_email in rows
        ],
    }
