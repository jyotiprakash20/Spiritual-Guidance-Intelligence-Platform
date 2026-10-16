from datetime import datetime

from uuid import UUID



from fastapi import APIRouter, Depends, HTTPException, Query, status

from pydantic import BaseModel, ConfigDict, Field

from sqlalchemy import func, select

from sqlalchemy.ext.asyncio import AsyncSession



from app.api.deps import get_current_user

from app.core.database import get_db

from app.models.relational import (
    ConsultationFeedback,
    ConsultationOutcome,
    ConsultationNote,

    Reading,

    SpiritualConsultantClient,

    User,

)

from app.schemas.user import UserRole

from app.services.consultant_analytics_service import (

    consultant_analytics_service,

)





router = APIRouter()





class ClientAssignmentCreate(BaseModel):

    client_id: UUID

    consultant_id: UUID | None = None





class ClientAssignmentOut(BaseModel):

    id: UUID

    consultant_id: UUID

    client_id: UUID

    status: str

    created_at: datetime | None = None



    model_config = ConfigDict(from_attributes=True)





def is_admin(user: User) -> bool:

    return user.role == UserRole.ADMIN.value





async def resolve_consultant(

    current_user: User,

    requested_consultant_id: UUID | None,

    db: AsyncSession,

) -> User:

    """Resolve the consultant whose data is being accessed."""



    if is_admin(current_user):

        if requested_consultant_id is None:

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="Administrators must provide consultant_id.",

            )



        result = await db.execute(

            select(User).where(User.id == requested_consultant_id)

        )

        consultant = result.scalar_one_or_none()



        if consultant is None:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="Spiritual Consultant not found.",

            )



        if consultant.role != UserRole.SPIRITUAL_CONSULTANT.value:

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="The selected user is not a Spiritual Consultant.",

            )



        return consultant



    if current_user.role != UserRole.SPIRITUAL_CONSULTANT.value:

        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail=(

                "Only Spiritual Consultants and Administrators "

                "can access this endpoint."

            ),

        )



    if (

        requested_consultant_id is not None

        and requested_consultant_id != current_user.id

    ):

        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail="You cannot manage another consultant's clients.",

        )



    return current_user





async def require_active_assignment(

    consultant_id: UUID,

    client_id: UUID,

    db: AsyncSession,

) -> SpiritualConsultantClient:

    result = await db.execute(

        select(SpiritualConsultantClient).where(

            SpiritualConsultantClient.consultant_id == consultant_id,

            SpiritualConsultantClient.client_id == client_id,

            SpiritualConsultantClient.status == "ACTIVE",

        )

    )

    assignment = result.scalar_one_or_none()



    if assignment is None:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="No active assignment exists for this client.",

        )



    return assignment





@router.get("/dashboard")

async def consultant_dashboard(

    consultant_id: UUID | None = Query(default=None),

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    """Return summary statistics for the consultant's active clients."""



    consultant = await resolve_consultant(

        current_user, consultant_id, db

    )



    client_ids_result = await db.execute(

        select(SpiritualConsultantClient.client_id).where(

            SpiritualConsultantClient.consultant_id == consultant.id,

            SpiritualConsultantClient.status == "ACTIVE",

        )

    )

    client_ids = list(client_ids_result.scalars().all())



    if not client_ids:

        return {

            "status": "success",

            "consultant_id": str(consultant.id),

            "stats": {

                "active_clients": 0,

                "total_readings": 0,

                "palmistry_readings": 0,

                "tarot_readings": 0,

                "synthesized_readings": 0,

                "average_insight_score": None,

            },

            "recent_activity": [],

        }



    stats_result = await db.execute(

        select(

            func.count(Reading.id),

            func.count(Reading.id).filter(

                Reading.reading_type == "PALMISTRY"

            ),

            func.count(Reading.id).filter(

                Reading.reading_type == "TAROT"

            ),

            func.count(Reading.id).filter(

                Reading.reading_type == "SYNTHESIZED"

            ),

            func.avg(Reading.overall_insight_score),

        ).where(Reading.user_id.in_(client_ids))

    )



    (

        total_readings,

        palmistry_readings,

        tarot_readings,

        synthesized_readings,

        average_score,

    ) = stats_result.one()



    recent_result = await db.execute(

        select(

            Reading.id,

            Reading.user_id,

            Reading.reading_type,

            Reading.overall_insight_score,

            Reading.created_at,

        )

        .where(Reading.user_id.in_(client_ids))

        .order_by(Reading.created_at.desc())

        .limit(10)

    )



    recent_activity = [

        {

            "reading_id": str(row.id),

            "client_id": str(row.user_id),

            "reading_type": row.reading_type,

            "overall_insight_score": (

                float(row.overall_insight_score)

                if row.overall_insight_score is not None

                else None

            ),

            "created_at": row.created_at,

        }

        for row in recent_result.all()

    ]



    return {

        "status": "success",

        "consultant_id": str(consultant.id),

        "stats": {

            "active_clients": len(client_ids),

            "total_readings": total_readings or 0,

            "palmistry_readings": palmistry_readings or 0,

            "tarot_readings": tarot_readings or 0,

            "synthesized_readings": synthesized_readings or 0,

            "average_insight_score": (

                round(float(average_score), 2)

                if average_score is not None

                else None

            ),

        },

        "recent_activity": recent_activity,

    }





@router.get("/analytics")

async def consultant_analytics(

    consultant_id: UUID | None = Query(default=None),

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    """Analyze saved readings belonging to active assigned clients."""



    consultant = await resolve_consultant(

        current_user, consultant_id, db

    )



    client_result = await db.execute(

        select(SpiritualConsultantClient.client_id).where(

            SpiritualConsultantClient.consultant_id == consultant.id,

            SpiritualConsultantClient.status == "ACTIVE",

        )

    )

    client_ids = list(client_result.scalars().all())



    if not client_ids:

        analytics = consultant_analytics_service.analyze(

            readings=[],

            client_count=0,

        )

        analytics["consultant_id"] = str(consultant.id)

        return analytics



    readings_result = await db.execute(

        select(

            Reading.reading_type,

            Reading.created_at,

            Reading.overall_insight_score,

            Reading.analysis_data,

        )

        .where(Reading.user_id.in_(client_ids))

        .order_by(Reading.created_at.desc())

    )



    readings = [

        {

            "reading_type": row.reading_type,

            "created_at": row.created_at,

            "overall_insight_score": (

                float(row.overall_insight_score)

                if row.overall_insight_score is not None

                else None

            ),

            "analysis_data": row.analysis_data or {},

        }

        for row in readings_result.all()

    ]



    analytics = consultant_analytics_service.analyze(

        readings=readings,

        client_count=len(client_ids),

    )

    analytics["consultant_id"] = str(consultant.id)



    return analytics





@router.get("/clients")

async def list_clients(

    consultant_id: UUID | None = Query(default=None),

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    consultant = await resolve_consultant(

        current_user, consultant_id, db

    )



    result = await db.execute(

        select(SpiritualConsultantClient)

        .where(

            SpiritualConsultantClient.consultant_id == consultant.id,

            SpiritualConsultantClient.status == "ACTIVE",

        )

        .order_by(SpiritualConsultantClient.created_at.desc())

    )

    assignments = result.scalars().all()



    clients = []

    for assignment in assignments:

        client_result = await db.execute(

            select(User).where(User.id == assignment.client_id)

        )

        client = client_result.scalar_one_or_none()



        if client is not None:

            clients.append({

                "assignment_id": str(assignment.id),

                "client_id": str(client.id),

                "email": client.email,

                "status": assignment.status,

                "assigned_at": assignment.created_at,

            })



    return {

        "status": "success",

        "consultant_id": str(consultant.id),

        "count": len(clients),

        "clients": clients,

    }





@router.post("/clients", status_code=status.HTTP_201_CREATED)

async def assign_client(

    payload: ClientAssignmentCreate,

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    consultant = await resolve_consultant(

        current_user, payload.consultant_id, db

    )



    if payload.client_id == consultant.id:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="A consultant cannot assign themselves as a client.",

        )



    client_result = await db.execute(

        select(User).where(User.id == payload.client_id)

    )

    client = client_result.scalar_one_or_none()



    if client is None:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Client not found.",

        )



    if client.role != UserRole.USER.value:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Only regular users can be assigned as clients.",

        )



    result = await db.execute(

        select(SpiritualConsultantClient).where(

            SpiritualConsultantClient.consultant_id == consultant.id,

            SpiritualConsultantClient.client_id == client.id,

        )

    )

    assignment = result.scalar_one_or_none()



    if assignment is not None:

        if assignment.status == "ACTIVE":

            raise HTTPException(

                status_code=status.HTTP_409_CONFLICT,

                detail="This client is already assigned to the consultant.",

            )



        assignment.status = "ACTIVE"

        assignment.created_at = datetime.utcnow()

    else:

        assignment = SpiritualConsultantClient(

            consultant_id=consultant.id,

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

            detail="Could not save the client assignment.",

        )



    return {

        "status": "success",

        "message": "Client assigned successfully.",

        "assignment": ClientAssignmentOut.model_validate(assignment),

    }





@router.get("/clients/{client_id}/readings")

async def get_client_readings(

    client_id: UUID,

    consultant_id: UUID | None = Query(default=None),

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    consultant = await resolve_consultant(

        current_user, consultant_id, db

    )



    await require_active_assignment(consultant.id, client_id, db)



    result = await db.execute(

        select(Reading)

        .where(Reading.user_id == client_id)

        .order_by(Reading.created_at.desc())

    )

    readings = result.scalars().all()



    return {

        "status": "success",

        "consultant_id": str(consultant.id),

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





@router.delete("/clients/{client_id}")

async def deactivate_client(

    client_id: UUID,

    consultant_id: UUID | None = Query(default=None),

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    consultant = await resolve_consultant(

        current_user, consultant_id, db

    )



    assignment = await require_active_assignment(

        consultant.id, client_id, db

    )

    assignment.status = "INACTIVE"



    try:

        await db.commit()

    except Exception:

        await db.rollback()

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail="Could not deactivate the client assignment.",

        )



    return {

        "status": "success",

        "message": (

            "Client assignment deactivated. Existing readings "

            "and reports were preserved."

        ),

        "consultant_id": str(consultant.id),

        "client_id": str(client_id),

        "assignment_status": "INACTIVE",

    }



# ---------------------------------------------------------------------
# Client feedback and consultation outcomes
# ---------------------------------------------------------------------

ALLOWED_OUTCOMES = {
    "HELPFUL",
    "NO_CHANGE",
    "DIFFICULT",
    "NOT_FOLLOWED_UP",
}


class ClientFeedbackCreate(BaseModel):
    consultant_id: UUID
    reading_id: UUID | None = None
    consultation_note_id: UUID | None = None
    rating: int = Field(ge=1, le=5)
    comments: str | None = Field(default=None, max_length=2000)


class ConsultationOutcomeCreate(BaseModel):
    reading_id: UUID | None = None
    consultation_note_id: UUID | None = None
    outcome: str
    notes: str | None = Field(default=None, max_length=2000)


async def _validate_client_reading(
    reading_id: UUID | None,
    client_id: UUID,
    db: AsyncSession,
) -> None:
    if reading_id is None:
        return
    result = await db.execute(
        select(Reading.id).where(
            Reading.id == reading_id,
            Reading.user_id == client_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected reading does not belong to this client.",
        )


async def _validate_client_note(
    note_id: UUID | None,
    consultant_id: UUID,
    client_id: UUID,
    db: AsyncSession,
) -> None:
    if note_id is None:
        return
    result = await db.execute(
        select(ConsultationNote.id).where(
            ConsultationNote.id == note_id,
            ConsultationNote.consultant_id == consultant_id,
            ConsultationNote.client_id == client_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected consultation note does not match this consultant and client.",
        )


@router.post(
    "/clients/{client_id}/feedback",
    status_code=status.HTTP_201_CREATED,
)
async def submit_client_feedback(
    client_id: UUID,
    payload: ClientFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Allow an assigned client to rate their consultant's session."""
    if current_user.id != client_id or current_user.role != UserRole.USER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clients may submit feedback only for their own account.",
        )

    await require_active_assignment(payload.consultant_id, client_id, db)
    await _validate_client_reading(payload.reading_id, client_id, db)
    await _validate_client_note(
        payload.consultation_note_id, payload.consultant_id, client_id, db
    )

    feedback = ConsultationFeedback(
        consultant_id=payload.consultant_id,
        client_id=client_id,
        reading_id=payload.reading_id,
        consultation_note_id=payload.consultation_note_id,
        rating=payload.rating,
        comments=payload.comments.strip() if payload.comments else None,
    )
    db.add(feedback)
    try:
        await db.commit()
        await db.refresh(feedback)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save client feedback.",
        )

    return {
        "status": "success",
        "feedback": {
            "id": str(feedback.id),
            "consultant_id": str(feedback.consultant_id),
            "client_id": str(feedback.client_id),
            "reading_id": str(feedback.reading_id) if feedback.reading_id else None,
            "consultation_note_id": (
                str(feedback.consultation_note_id)
                if feedback.consultation_note_id else None
            ),
            "rating": feedback.rating,
            "comments": feedback.comments,
            "submitted_at": feedback.submitted_at,
        },
    }


@router.post(
    "/clients/{client_id}/outcomes",
    status_code=status.HTTP_201_CREATED,
)
async def record_consultation_outcome(
    client_id: UUID,
    payload: ConsultationOutcomeCreate,
    consultant_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Let a consultant record a client's reported follow-up outcome."""
    consultant = await resolve_consultant(current_user, consultant_id, db)
    await require_active_assignment(consultant.id, client_id, db)

    outcome_value = payload.outcome.strip().upper()
    if outcome_value not in ALLOWED_OUTCOMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="outcome must be one of: HELPFUL, NO_CHANGE, DIFFICULT, NOT_FOLLOWED_UP.",
        )

    await _validate_client_reading(payload.reading_id, client_id, db)
    await _validate_client_note(
        payload.consultation_note_id, consultant.id, client_id, db
    )

    outcome = ConsultationOutcome(
        consultant_id=consultant.id,
        client_id=client_id,
        reading_id=payload.reading_id,
        consultation_note_id=payload.consultation_note_id,
        outcome=outcome_value,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(outcome)
    try:
        await db.commit()
        await db.refresh(outcome)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save consultation outcome.",
        )

    return {
        "status": "success",
        "outcome": {
            "id": str(outcome.id),
            "consultant_id": str(outcome.consultant_id),
            "client_id": str(outcome.client_id),
            "reading_id": str(outcome.reading_id) if outcome.reading_id else None,
            "consultation_note_id": (
                str(outcome.consultation_note_id)
                if outcome.consultation_note_id else None
            ),
            "outcome": outcome.outcome,
            "notes": outcome.notes,
            "recorded_at": outcome.recorded_at,
        },
    }


@router.get("/effectiveness")
async def consultant_effectiveness(
    consultant_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Summarize recorded feedback and outcomes; these do not prove causation."""
    consultant = await resolve_consultant(current_user, consultant_id, db)
    client_ids_result = await db.execute(
        select(SpiritualConsultantClient.client_id).where(
            SpiritualConsultantClient.consultant_id == consultant.id,
            SpiritualConsultantClient.status == "ACTIVE",
        )
    )
    client_ids = list(client_ids_result.scalars().all())

    if not client_ids:
        return {
            "status": "success",
            "consultant_id": str(consultant.id),
            "feedback": {"count": 0, "average_rating": None, "rating_distribution": {}},
            "outcomes": {"count": 0, "by_outcome": {}, "helpful_rate_percent": None},
            "disclaimer": "These are self-reported observations and do not establish that guidance caused an outcome.",
        }

    feedback_result = await db.execute(
        select(
            func.count(ConsultationFeedback.id),
            func.avg(ConsultationFeedback.rating),
        ).where(
            ConsultationFeedback.consultant_id == consultant.id,
            ConsultationFeedback.client_id.in_(client_ids),
        )
    )
    feedback_count, average_rating = feedback_result.one()

    rating_result = await db.execute(
        select(ConsultationFeedback.rating, func.count(ConsultationFeedback.id))
        .where(
            ConsultationFeedback.consultant_id == consultant.id,
            ConsultationFeedback.client_id.in_(client_ids),
        )
        .group_by(ConsultationFeedback.rating)
    )
    rating_distribution = {
        str(rating): count for rating, count in rating_result.all()
    }

    outcome_result = await db.execute(
        select(ConsultationOutcome.outcome, func.count(ConsultationOutcome.id))
        .where(
            ConsultationOutcome.consultant_id == consultant.id,
            ConsultationOutcome.client_id.in_(client_ids),
        )
        .group_by(ConsultationOutcome.outcome)
    )
    by_outcome = {outcome: count for outcome, count in outcome_result.all()}
    measured_total = sum(
        by_outcome.get(key, 0)
        for key in ("HELPFUL", "NO_CHANGE", "DIFFICULT")
    )
    helpful_rate = (
        round(by_outcome.get("HELPFUL", 0) / measured_total * 100, 2)
        if measured_total else None
    )

    return {
        "status": "success",
        "consultant_id": str(consultant.id),
        "feedback": {
            "count": int(feedback_count or 0),
            "average_rating": round(float(average_rating), 2) if average_rating is not None else None,
            "rating_distribution": rating_distribution,
        },
        "outcomes": {
            "count": sum(by_outcome.values()),
            "by_outcome": by_outcome,
            "helpful_rate_percent": helpful_rate,
        },
        "disclaimer": "These are self-reported observations and do not establish that guidance caused an outcome.",
    }

