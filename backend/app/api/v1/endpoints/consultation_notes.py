import logging

from datetime import datetime, timezone

from uuid import UUID







from fastapi import APIRouter, Depends, HTTPException, Query, status



from pydantic import BaseModel, ConfigDict, Field



from sqlalchemy import select



from sqlalchemy.ext.asyncio import AsyncSession







from app.api.deps import get_current_user



from app.core.database import get_db



from app.models.relational import (



    ConsultationNote,



    Reading,



    SpiritualConsultantClient,



    User,



)



from app.schemas.user import UserRole











logger = logging.getLogger(__name__)



router = APIRouter()







ALLOWED_PROGRESS_STATUSES = {



    "IN_PROGRESS",



    "COMPLETED",



    "ON_HOLD",



}





def normalize_datetime_for_db(value: datetime | None) -> datetime | None:

    """Normalize datetimes to naive UTC for PostgreSQL TIMESTAMP WITHOUT TIME ZONE."""

    if value is None:

        return None



    if value.tzinfo is not None and value.utcoffset() is not None:

        return value.astimezone(timezone.utc).replace(tzinfo=None)



    # Existing naive values are treated as UTC.

    return value











# ---------------------------------------------------------



# Request and response schemas



# ---------------------------------------------------------







class ConsultationNoteCreate(BaseModel):



    client_id: UUID



    reading_id: UUID | None = None



    title: str = Field(min_length=1, max_length=200)



    session_notes: str = Field(min_length=1)



    follow_up_actions: list[str] = Field(default_factory=list)



    progress_status: str = "IN_PROGRESS"



    next_follow_up_at: datetime | None = None







    model_config = ConfigDict(str_strip_whitespace=True)











class ConsultationNoteUpdate(BaseModel):



    title: str | None = Field(default=None, min_length=1, max_length=200)



    session_notes: str | None = Field(default=None, min_length=1)



    follow_up_actions: list[str] | None = None



    progress_status: str | None = None



    next_follow_up_at: datetime | None = None







    model_config = ConfigDict(str_strip_whitespace=True)











class ConsultationNoteOut(BaseModel):



    id: UUID



    consultant_id: UUID



    client_id: UUID



    reading_id: UUID | None



    title: str



    session_notes: str



    follow_up_actions: list[str]



    progress_status: str



    next_follow_up_at: datetime | None



    created_at: datetime



    updated_at: datetime







    model_config = ConfigDict(from_attributes=True)











# ---------------------------------------------------------



# Authorization



# ---------------------------------------------------------







def require_note_viewer(current_user: User) -> None:



    """Consultants and administrators may view consultation notes."""



    if current_user.role not in {



        UserRole.SPIRITUAL_CONSULTANT.value,



        UserRole.ADMIN.value,



    }:



        raise HTTPException(



            status_code=status.HTTP_403_FORBIDDEN,



            detail=(



                "Only Spiritual Consultants and Administrators "



                "can view consultation notes."



            ),



        )











def require_note_manager(current_user: User) -> None:



    """Only spiritual consultants may modify consultation notes."""



    if current_user.role != UserRole.SPIRITUAL_CONSULTANT.value:



        raise HTTPException(



            status_code=status.HTTP_403_FORBIDDEN,



            detail=(



                "Only Spiritual Consultants can create, update, "



                "or delete consultation notes."



            ),



        )











async def resolve_consultant_id(



    requested_consultant_id: UUID | None,



    current_user: User,



    db: AsyncSession,



) -> UUID:



    """



    Consultants may access only their own notes.



    Administrators must explicitly select a valid consultant to view.



    """



    require_note_viewer(current_user)







    if current_user.role == UserRole.ADMIN.value:



        if requested_consultant_id is None:



            raise HTTPException(



                status_code=status.HTTP_400_BAD_REQUEST,



                detail=(



                    "Administrators must provide consultant_id "



                    "to view consultation notes."



                ),



            )







        result = await db.execute(



            select(User).where(User.id == requested_consultant_id)



        )



        consultant = result.scalar_one_or_none()







        if (



            consultant is None



            or consultant.role != UserRole.SPIRITUAL_CONSULTANT.value



        ):



            raise HTTPException(



                status_code=status.HTTP_404_NOT_FOUND,



                detail="Spiritual Consultant not found.",



            )







        return consultant.id







    if (



        requested_consultant_id is not None



        and requested_consultant_id != current_user.id



    ):



        raise HTTPException(



            status_code=status.HTTP_403_FORBIDDEN,



            detail="You cannot access another consultant's notes.",



        )







    return current_user.id











async def require_active_assignment(



    consultant_id: UUID,



    client_id: UUID,



    db: AsyncSession,



) -> None:



    result = await db.execute(



        select(SpiritualConsultantClient.id).where(



            SpiritualConsultantClient.consultant_id == consultant_id,



            SpiritualConsultantClient.client_id == client_id,



            SpiritualConsultantClient.status == "ACTIVE",



        )



    )







    if result.scalar_one_or_none() is None:



        raise HTTPException(



            status_code=status.HTTP_404_NOT_FOUND,



            detail="No active assignment exists for this client.",



        )











async def validate_reading(



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











def validate_progress_status(value: str | None) -> None:



    if value is not None and value not in ALLOWED_PROGRESS_STATUSES:



        raise HTTPException(



            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,



            detail=(



                "progress_status must be one of: "



                "IN_PROGRESS, COMPLETED, ON_HOLD."



            ),



        )











async def get_note_for_consultant(



    note_id: UUID,



    consultant_id: UUID,



    db: AsyncSession,



) -> ConsultationNote:



    result = await db.execute(



        select(ConsultationNote).where(



            ConsultationNote.id == note_id,



            ConsultationNote.consultant_id == consultant_id,



        )



    )



    note = result.scalar_one_or_none()







    if note is None:



        raise HTTPException(



            status_code=status.HTTP_404_NOT_FOUND,



            detail="Consultation note not found.",



        )







    await require_active_assignment(



        consultant_id,



        note.client_id,



        db,



    )







    return note











# ---------------------------------------------------------



# Create consultation note - consultants only



# ---------------------------------------------------------







@router.post("", status_code=status.HTTP_201_CREATED)



async def create_consultation_note(



    payload: ConsultationNoteCreate,



    consultant_id: UUID | None = Query(default=None),



    current_user: User = Depends(get_current_user),



    db: AsyncSession = Depends(get_db),



):



    require_note_manager(current_user)







    resolved_consultant_id = await resolve_consultant_id(



        consultant_id,



        current_user,



        db,



    )







    await require_active_assignment(



        resolved_consultant_id,



        payload.client_id,



        db,



    )







    validate_progress_status(payload.progress_status)







    await validate_reading(



        payload.reading_id,



        payload.client_id,



        db,



    )







    note = ConsultationNote(



        consultant_id=resolved_consultant_id,



        client_id=payload.client_id,



        reading_id=payload.reading_id,



        title=payload.title,



        session_notes=payload.session_notes,



        follow_up_actions=payload.follow_up_actions,



        progress_status=payload.progress_status,



        next_follow_up_at=normalize_datetime_for_db(payload.next_follow_up_at),



    )







    db.add(note)







    try:



        await db.commit()



        await db.refresh(note)



    except Exception:

        logger.exception(

            "Failed to create consultation note "

            "(consultant_id=%s, client_id=%s, reading_id=%s)",

            resolved_consultant_id,

            payload.client_id,

            payload.reading_id,

        )

        await db.rollback()





        raise HTTPException(



            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,



            detail="Could not save the consultation note.",



        )







    return {



        "status": "success",



        "note": ConsultationNoteOut.model_validate(note),



    }











# ---------------------------------------------------------



# List consultation notes - consultants and administrators



# ---------------------------------------------------------







@router.get("")



async def list_consultation_notes(



    client_id: UUID | None = Query(default=None),



    consultant_id: UUID | None = Query(default=None),



    current_user: User = Depends(get_current_user),



    db: AsyncSession = Depends(get_db),



):



    resolved_consultant_id = await resolve_consultant_id(



        consultant_id,



        current_user,



        db,



    )







    query = select(ConsultationNote).where(



        ConsultationNote.consultant_id == resolved_consultant_id



    )







    if client_id is not None:



        await require_active_assignment(



            resolved_consultant_id,



            client_id,



            db,



        )



        query = query.where(



            ConsultationNote.client_id == client_id



        )



    else:



        active_clients = select(



            SpiritualConsultantClient.client_id



        ).where(



            SpiritualConsultantClient.consultant_id



            == resolved_consultant_id,



            SpiritualConsultantClient.status == "ACTIVE",



        )







        query = query.where(



            ConsultationNote.client_id.in_(active_clients)



        )







    query = query.order_by(



        ConsultationNote.created_at.desc()



    )







    result = await db.execute(query)



    notes = result.scalars().all()







    return {



        "status": "success",



        "consultant_id": str(resolved_consultant_id),



        "count": len(notes),



        "notes": [



            ConsultationNoteOut.model_validate(note)



            for note in notes



        ],



    }











# ---------------------------------------------------------



# Retrieve one note - consultants and administrators



# ---------------------------------------------------------







@router.get("/{note_id}")



async def get_consultation_note(



    note_id: UUID,



    consultant_id: UUID | None = Query(default=None),



    current_user: User = Depends(get_current_user),



    db: AsyncSession = Depends(get_db),



):



    resolved_consultant_id = await resolve_consultant_id(



        consultant_id,



        current_user,



        db,



    )







    note = await get_note_for_consultant(



        note_id,



        resolved_consultant_id,



        db,



    )







    return {



        "status": "success",



        "note": ConsultationNoteOut.model_validate(note),



    }











# ---------------------------------------------------------



# Update consultation note - consultants only



# ---------------------------------------------------------







@router.patch("/{note_id}")



async def update_consultation_note(



    note_id: UUID,



    payload: ConsultationNoteUpdate,



    consultant_id: UUID | None = Query(default=None),



    current_user: User = Depends(get_current_user),



    db: AsyncSession = Depends(get_db),



):



    require_note_manager(current_user)







    resolved_consultant_id = await resolve_consultant_id(



        consultant_id,



        current_user,



        db,



    )







    note = await get_note_for_consultant(



        note_id,



        resolved_consultant_id,



        db,



    )







    updates = payload.model_dump(exclude_unset=True)







    if not updates:



        raise HTTPException(



            status_code=status.HTTP_400_BAD_REQUEST,



            detail="Provide at least one field to update.",



        )







    validate_progress_status(updates.get("progress_status"))







    for field, value in updates.items():



        if field in {"title", "session_notes"}:



            if value is None:



                raise HTTPException(



                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,



                    detail=f"{field} cannot be null.",



                )







            value = value.strip()







            if not value:



                raise HTTPException(



                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,



                    detail=f"{field} cannot be blank.",



                )







        if field == "follow_up_actions" and value is not None:



            if not all(



                isinstance(action, str) and action.strip()



                for action in value



            ):



                raise HTTPException(



                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,



                    detail=(



                        "Every follow-up action must be a "



                        "non-empty string."



                    ),



                )



            value = [action.strip() for action in value]







        setattr(note, field, value)







    if "next_follow_up_at" in updates:



        note.next_follow_up_at = normalize_datetime_for_db(

            updates["next_follow_up_at"]

        )







    note.updated_at = datetime.utcnow()







    try:



        await db.commit()



        await db.refresh(note)



    except Exception:



        await db.rollback()



        raise HTTPException(



            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,



            detail="Could not update the consultation note.",



        )







    return {



        "status": "success",



        "note": ConsultationNoteOut.model_validate(note),



    }











# ---------------------------------------------------------



# Delete consultation note - consultants only



# ---------------------------------------------------------







@router.delete("/{note_id}")



async def delete_consultation_note(



    note_id: UUID,



    consultant_id: UUID | None = Query(default=None),



    current_user: User = Depends(get_current_user),



    db: AsyncSession = Depends(get_db),



):



    require_note_manager(current_user)







    resolved_consultant_id = await resolve_consultant_id(



        consultant_id,



        current_user,



        db,



    )







    note = await get_note_for_consultant(



        note_id,



        resolved_consultant_id,



        db,



    )







    try:



        await db.delete(note)



        await db.commit()



    except Exception:



        await db.rollback()



        raise HTTPException(



            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,



            detail="Could not delete the consultation note.",



        )







    return {



        "status": "success",



        "message": "Consultation note deleted.",



        "note_id": str(note_id),



    }
