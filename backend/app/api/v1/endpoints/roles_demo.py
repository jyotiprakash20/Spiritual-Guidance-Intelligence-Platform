
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.schemas.user import UserRole
from app.models.relational import (
    User,
    Reading,
    Report,
    TarotReaderClient,
)

router = APIRouter()


@router.get("/user-area")
async def user_dashboard(
    current_user: User = Depends(get_current_user),
):
    """Return dashboard information for a seeker."""
    return {
        "message": "Welcome to the Seeker area",
        "user_email": current_user.email,
        "role": current_user.role,
    }


@router.get("/tarot-reader-workspace")
async def tarot_reader_dashboard(
    current_user: User = Depends(
        require_roles([UserRole.TAROT_READER])
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Return analytics and recent sessions for a Tarot Reader's
    currently assigned, active clients.
    """

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=30)

    # 1. Count distinct active clients assigned to this reader.
    active_clients_result = await db.execute(
        select(
            func.count(distinct(TarotReaderClient.client_id))
        ).where(
            TarotReaderClient.reader_id == current_user.id,
            TarotReaderClient.status == "ACTIVE",
        )
    )
    active_clients = active_clients_result.scalar_one() or 0

    # 2. Select readings belonging to the reader's active clients.
    # EXISTS avoids duplicate readings if matching assignment rows
    # are duplicated.
    active_client_exists = (
        select(TarotReaderClient.id)
        .where(
            TarotReaderClient.reader_id == current_user.id,
            TarotReaderClient.client_id == Reading.user_id,
            TarotReaderClient.status == "ACTIVE",
        )
        .exists()
    )

    readings_result = await db.execute(
        select(Reading)
        .where(active_client_exists)
        .order_by(Reading.created_at.desc())
    )
    readings = readings_result.scalars().all()

    # 3. Calculate reading analytics.
    readings_last_30_days = 0
    scores = []
    recent_sessions = []

    reading_ids = [reading.id for reading in readings]

    for reading in readings:
        created_at = reading.created_at

        if created_at is not None:
            # Treat naive database timestamps as UTC.
            if created_at.tzinfo is None:
                created_at = created_at.replace(
                    tzinfo=timezone.utc
                )

            if period_start <= created_at <= now:
                readings_last_30_days += 1

        score = reading.overall_insight_score

        if score is not None:
            scores.append(float(score))

        # The readings are ordered newest first.
        if len(recent_sessions) < 10:
            recent_sessions.append(
                {
                    "reading_id": str(reading.id),
                    "client_id": str(reading.user_id),
                    "reading_type": reading.reading_type,
                    "created_at": (
                        reading.created_at.isoformat()
                        if reading.created_at is not None
                        else None
                    ),
                    "insight_score": (
                        float(score)
                        if score is not None
                        else None
                    ),
                }
            )

    # 4. Count distinct reports associated with these readings.
    # This assumes Report.reading_id is the authoritative
    # relationship between a report and its reading.
    reports_available = 0

    if reading_ids:
        reports_result = await db.execute(
            select(
                func.count(distinct(Report.id))
            ).where(
                Report.reading_id.in_(reading_ids)
            )
        )
        reports_available = reports_result.scalar_one() or 0

    # 5. Average non-null insight scores across all selected readings.
    average_insight_score = (
        round(sum(scores) / len(scores), 1)
        if scores
        else None
    )

    # 6. Return the workspace response.
    return {
        "status": "success",
        "message": "Welcome to the Tarot Reading Desk",
        "user_email": current_user.email,
        "role": current_user.role,
        "analytics": {
            "active_clients": active_clients,
            "total_readings": len(readings),
            "readings_last_30_days": readings_last_30_days,
            "reports_available": reports_available,
            "average_insight_score": average_insight_score,
        },
        "recent_sessions": recent_sessions,
    }


@router.get("/spiritual-consultant-workspace")
async def spiritual_consultant_dashboard(
    current_user: User = Depends(
        require_roles([UserRole.SPIRITUAL_CONSULTANT])
    ),
):
    """Return dashboard information for a spiritual consultant."""
    return {
        "message": "Welcome to the Spiritual Consultation Suite",
        "user_email": current_user.email,
        "role": current_user.role,
    }


@router.get("/admin-panel")
async def admin_panel(
    current_user: User = Depends(
        require_roles([UserRole.ADMIN])
    ),
):
    """Return dashboard information for an administrator."""
    return {
        "message": "Welcome to the Master Administration Console",
        "user_email": current_user.email,
        "role": current_user.role,
    }
