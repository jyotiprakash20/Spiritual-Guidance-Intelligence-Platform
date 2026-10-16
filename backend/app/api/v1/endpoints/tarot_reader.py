
from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.relational import (
    User,
    Reading,
    Report,
    TarotReaderClient,
)
from app.schemas.user import UserRole


router = APIRouter()


# -------------------------------------------------------------------
# REQUEST SCHEMAS
# -------------------------------------------------------------------

class ClientAssignmentCreate(BaseModel):
    client_id: UUID
    reader_id: Optional[UUID] = None


class ClientAssignmentOut(BaseModel):
    id: UUID
    reader_id: UUID
    client_id: UUID
    status: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN.value


async def get_reader_for_assignment(
    current_user: User,
    requested_reader_id: Optional[UUID],
    db: AsyncSession,
) -> User:
    """
    Tarot Readers can act only as themselves.
    Administrators must explicitly choose the reader.
    """

    if is_admin(current_user):
        if requested_reader_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators must provide reader_id.",
            )

        result = await db.execute(
            select(User).where(User.id == requested_reader_id)
        )
        reader = result.scalar_one_or_none()

        if reader is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reader not found.",
            )

        if reader.role != UserRole.TAROT_READER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected user is not a Tarot Reader.",
            )

        return reader

    if (
        requested_reader_id is not None
        and requested_reader_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create assignments for another reader.",
        )

    return current_user


async def get_active_assignment(
    client_id: UUID,
    current_user: User,
    db: AsyncSession,
    reader_id: Optional[UUID] = None,
) -> TarotReaderClient:
    """
    Find an active assignment authorizing access to a client.

    Readers can access only their own assignments.
    Administrators must specify the reader whose assignment
    they want to inspect.
    """

    effective_reader_id = current_user.id

    if is_admin(current_user):
        if reader_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators must provide reader_id.",
            )

        effective_reader_id = reader_id

    elif reader_id is not None and reader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another reader's assignments.",
        )

    result = await db.execute(
        select(TarotReaderClient).where(
            TarotReaderClient.reader_id == effective_reader_id,
            TarotReaderClient.client_id == client_id,
            TarotReaderClient.status == "ACTIVE",
        )
    )

    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active assignment exists for this client.",
        )

    return assignment


# -------------------------------------------------------------------
# LIST ASSIGNED CLIENTS
# GET /api/v1/tarot-reader/clients
# -------------------------------------------------------------------

@router.get("/clients")
async def list_clients(
    reader_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(
        require_roles([UserRole.TAROT_READER])
    ),
    db: AsyncSession = Depends(get_db),
):
    """List active client assignments for the current reader."""

    effective_reader_id = current_user.id

    if is_admin(current_user):
        if reader_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators must provide reader_id.",
            )

        result = await db.execute(
            select(User).where(User.id == reader_id)
        )
        reader = result.scalar_one_or_none()

        if (
            reader is None
            or reader.role != UserRole.TAROT_READER.value
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarot Reader not found.",
            )

        effective_reader_id = reader_id

    elif reader_id is not None and reader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot view another reader's clients.",
        )

    result = await db.execute(
        select(TarotReaderClient, User)
        .join(User, User.id == TarotReaderClient.client_id)
        .where(
            TarotReaderClient.reader_id == effective_reader_id,
            TarotReaderClient.status == "ACTIVE",
        )
        .order_by(TarotReaderClient.created_at.desc())
    )

    rows = result.all()

    return {
        "status": "success",
        "reader_id": str(effective_reader_id),
        "count": len(rows),
        "clients": [
            {
                "assignment_id": str(assignment.id),
                "client_id": str(client.id),
                "client_email": client.email,
                "status": assignment.status,
                "assigned_at": assignment.created_at,
            }
            for assignment, client in rows
        ],
    }


# -------------------------------------------------------------------
# ASSIGN A CLIENT
# POST /api/v1/tarot-reader/clients
# -------------------------------------------------------------------

@router.post(
    "/clients",
    status_code=status.HTTP_201_CREATED,
)
async def assign_client(
    payload: ClientAssignmentCreate,
    current_user: User = Depends(
        require_roles([UserRole.TAROT_READER])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Create or reactivate a reader-client assignment."""

    reader = await get_reader_for_assignment(
        current_user=current_user,
        requested_reader_id=payload.reader_id,
        db=db,
    )

    if reader.id == payload.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Tarot Reader cannot assign themselves as a client.",
        )

    result = await db.execute(
        select(User).where(User.id == payload.client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client user not found.",
        )

    if client.role != UserRole.USER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ordinary User accounts can be assigned as clients.",
        )

    result = await db.execute(
        select(TarotReaderClient).where(
            TarotReaderClient.reader_id == reader.id,
            TarotReaderClient.client_id == client.id,
        )
    )
    assignment = result.scalar_one_or_none()

    if assignment is not None:
        if assignment.status == "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This client is already assigned to the reader.",
            )

        assignment.status = "ACTIVE"

    else:
        assignment = TarotReaderClient(
            reader_id=reader.id,
            client_id=client.id,
            status="ACTIVE",
        )
        db.add(assignment)

    try:
        await db.commit()
        await db.refresh(assignment)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Client assignment could not be saved.",
        )

    return {
        "status": "success",
        "message": "Client assigned successfully.",
        "assignment": ClientAssignmentOut.model_validate(assignment),
    }


# -------------------------------------------------------------------
# LIST A CLIENT'S READINGS
# GET /api/v1/tarot-reader/clients/{client_id}/readings
# -------------------------------------------------------------------

@router.get("/clients/{client_id}/readings")
async def list_client_readings(
    client_id: UUID,
    reader_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(
        require_roles([UserRole.TAROT_READER])
    ),
    db: AsyncSession = Depends(get_db),
):
    """List readings for a client actively assigned to this reader."""

    await get_active_assignment(
        client_id=client_id,
        current_user=current_user,
        db=db,
        reader_id=reader_id,
    )

    result = await db.execute(
        select(Reading)
        .where(Reading.user_id == client_id)
        .order_by(Reading.created_at.desc())
    )
    readings = result.scalars().all()

    return {
        "status": "success",
        "client_id": str(client_id),
        "count": len(readings),
        "readings": [
            {
                "reading_id": str(reading.id),
                "reading_type": reading.reading_type,
                "overall_insight_score": (
                    float(reading.overall_insight_score)
                    if reading.overall_insight_score is not None
                    else None
                ),
                "created_at": reading.created_at,
            }
            for reading in readings
        ],
    }


# -------------------------------------------------------------------
# LIST SAVED REPORTS
# GET /api/v1/tarot-reader/reports
# -------------------------------------------------------------------

@router.get("/reports")
async def list_saved_reports(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(
        require_roles([UserRole.TAROT_READER])
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    List saved reports belonging to clients actively assigned
    to the authenticated Tarot Reader.

    Pagination:
        limit: Number of reports to return (1-100).
        offset: Number of reports to skip.
    """

    query = (
        select(Report, Reading, User)
        .join(
            Reading,
            Report.reading_id == Reading.id,
        )
        .join(
            User,
            Report.user_id == User.id,
        )
        .join(
            TarotReaderClient,
            TarotReaderClient.client_id == Report.user_id,
        )
        .where(
            TarotReaderClient.reader_id == current_user.id,
            TarotReaderClient.status == "ACTIVE",
            Reading.user_id == Report.user_id,
        )
        .order_by(
            Reading.created_at.desc(),
            Report.id.desc(),
        )
        .offset(offset)
        .limit(limit + 1)
    )

    result = await db.execute(query)
    rows = result.all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    reports = [
        {
            "report_id": str(report.id),
            "report_title": report.report_title,
            "report_summary": report.report_summary,
            "actionable_steps": report.actionable_steps,
            "client_id": str(client.id),
            "client_email": client.email,
            "reading_id": str(reading.id),
            "reading_type": reading.reading_type,
            "reading_created_at": (
                reading.created_at.isoformat()
                if reading.created_at
                else None
            ),
            "overall_insight_score": (
                float(reading.overall_insight_score)
                if reading.overall_insight_score is not None
                else None
            ),
        }
        for report, reading, client in rows
    ]

    return {
        "status": "success",
        "count": len(reports),
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "reports": reports,
    }


# -------------------------------------------------------------------
# DEACTIVATE A CLIENT ASSIGNMENT
# DELETE /api/v1/tarot-reader/clients/{client_id}
# -------------------------------------------------------------------

@router.delete("/clients/{client_id}")
async def deactivate_client(
    client_id: UUID,
    reader_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(
        require_roles([UserRole.TAROT_READER])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate an assignment without deleting readings or reports."""

    assignment = await get_active_assignment(
        client_id=client_id,
        current_user=current_user,
        db=db,
        reader_id=reader_id,
    )

    assignment.status = "INACTIVE"

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Client assignment could not be deactivated.",
        )

    return {
        "status": "success",
        "message": "Client assignment deactivated successfully.",
        "assignment_id": str(assignment.id),
        "client_id": str(assignment.client_id),
        "reader_id": str(assignment.reader_id),
        "assignment_status": assignment.status,
    }


# -------------------------------------------------------------------
# GET A CLIENT'S SAVED READING DETAILS
# GET /api/v1/tarot-reader/clients/{client_id}/readings/{reading_id}
# -------------------------------------------------------------------

@router.get("/clients/{client_id}/readings/{reading_id}")
async def get_client_reading_details(
    client_id: UUID,
    reading_id: UUID,
    reader_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(
        require_roles([UserRole.TAROT_READER])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a saved reading and its report, if one exists."""

    await get_active_assignment(
        client_id=client_id,
        current_user=current_user,
        db=db,
        reader_id=reader_id,
    )

    result = await db.execute(
        select(Reading).where(
            Reading.id == reading_id,
            Reading.user_id == client_id,
        )
    )
    reading = result.scalar_one_or_none()

    if reading is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading not found for this client.",
        )

    report_result = await db.execute(
        select(Report)
        .where(
            Report.reading_id == reading.id,
            Report.user_id == client_id,
        )
        .order_by(Report.id.desc())
        .limit(1)
    )
    report = report_result.scalars().first()

    report_data = None

    if report is not None:
        report_data = {
            "report_id": str(report.id),
            "report_title": report.report_title,
            "report_summary": report.report_summary,
            "actionable_steps": report.actionable_steps,
        }

    return {
        "status": "success",
        "reading": {
            "reading_id": str(reading.id),
            "reading_type": reading.reading_type,
            "created_at": (
                reading.created_at.isoformat()
                if reading.created_at
                else None
            ),
            "overall_insight_score": (
                float(reading.overall_insight_score)
                if reading.overall_insight_score is not None
                else None
            ),
            "analysis_data": reading.analysis_data or {},
        },
        "report": report_data,
    }
