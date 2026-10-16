
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.models.relational import (
    User,
    Profile,
    ProfessionalAvailability,
    ConsultationBooking,
    ConsultationChatMessage,
)
from app.schemas.user import TokenPayload, UserRole



router = APIRouter()


# ===========================================================================
# REQUEST SCHEMAS
# ===========================================================================

class AvailabilityUpdate(BaseModel):
    is_online: bool | None = None
    accepting_bookings: bool | None = None
    supports_chat: bool | None = None
    supports_voice: bool | None = None
    supports_video: bool | None = None


class BookingCreate(BaseModel):
    professional_id: UUID
    consultation_mode: Literal["CHAT", "VOICE", "VIDEO"]
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=120)


# ===========================================================================
# HELPERS
# ===========================================================================

PROFESSIONAL_ROLES = {
    UserRole.TAROT_READER.value,
    UserRole.SPIRITUAL_CONSULTANT.value,
}

ACTIVE_BOOKING_STATUSES = ["PENDING", "CONFIRMED"]


def normalize_datetime(value: datetime) -> datetime:
    """Normalize an appointment time to naive UTC for PostgreSQL TIMESTAMP."""
    if value.tzinfo is None:
        return value

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def availability_to_dict(availability):
    return {
        "is_online": availability.is_online,
        "accepting_bookings": availability.accepting_bookings,
        "supports_chat": availability.supports_chat,
        "supports_voice": availability.supports_voice,
        "supports_video": availability.supports_video,
    }


async def get_availability_for_professional(
    professional_id: UUID,
    db: AsyncSession,
):
    result = await db.execute(
        select(ProfessionalAvailability).where(
            ProfessionalAvailability.professional_id == professional_id
        )
    )
    return result.scalar_one_or_none()


def booking_to_dict(booking):
    scheduled_at = booking.scheduled_at

    return {
        "id": str(booking.id),
        "client_id": str(booking.client_id),
        "professional_id": str(booking.professional_id),
        "professional_type": booking.professional_type,
        "consultation_mode": booking.consultation_mode,
        "scheduled_at": (
            scheduled_at.isoformat() + "Z"
            if scheduled_at.tzinfo is None
            else scheduled_at.isoformat()
        ),
        "duration_minutes": booking.duration_minutes,
        "status": booking.status,
        "amount": float(booking.amount),
        "created_at": (
            booking.created_at.isoformat()
            if booking.created_at
            else None
        ),
    }


# ===========================================================================
# LIST PROFESSIONALS
# GET /api/v1/consultation-hub/professionals
# ===========================================================================

@router.get("/professionals")
async def list_professionals(
    professional_type: str = Query(
        default="ALL",
        description="ALL, TAROT_READER, or SPIRITUAL_CONSULTANT",
    ),
    db: AsyncSession = Depends(get_db),
):
    professional_type = professional_type.upper()

    allowed_types = {
        "ALL",
        "TAROT_READER",
        "SPIRITUAL_CONSULTANT",
    }

    if professional_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "professional_type must be ALL, TAROT_READER, "
                "or SPIRITUAL_CONSULTANT."
            ),
        )

    role_map = {
        "TAROT_READER": UserRole.TAROT_READER.value,
        "SPIRITUAL_CONSULTANT": UserRole.SPIRITUAL_CONSULTANT.value,
    }

    query = (
        select(User, Profile)
        .outerjoin(Profile, Profile.user_id == User.id)
    )

    if professional_type == "ALL":
        query = query.where(User.role.in_(list(PROFESSIONAL_ROLES)))
    else:
        query = query.where(User.role == role_map[professional_type])

    query = query.order_by(User.created_at.desc())

    result = await db.execute(query)
    rows = result.all()

    professionals = []

    for user, profile in rows:
        availability = await get_availability_for_professional(
            user.id, db
        )

        is_online = (
            availability.is_online if availability else False
        )
        accepting_bookings = (
            availability.accepting_bookings if availability else False
        )
        supports_chat = availability.supports_chat if availability else False
        supports_voice = availability.supports_voice if availability else False
        supports_video = availability.supports_video if availability else False

        professionals.append({
            "id": str(user.id),
            "name": (
                profile.full_name
                if profile and profile.full_name
                else user.email.split("@")[0]
            ),
            "professional_type": user.role,
            "interests": profile.interests if profile else None,
            "spiritual_goals": (
                profile.spiritual_goals if profile else None
            ),
            "is_online": is_online,
            "accepting_bookings": accepting_bookings,
            "supported_modes": [
                mode
                for mode, enabled in [
                    ("CHAT", supports_chat),
                    ("VOICE", supports_voice),
                    ("VIDEO", supports_video),
                ]
                if enabled
            ],
        })

    return {
        "status": "success",
        "count": len(professionals),
        "professionals": professionals,
    }


# ===========================================================================
# GET MY AVAILABILITY
# GET /api/v1/consultation-hub/me/availability
# ===========================================================================

@router.get("/me/availability")
async def get_my_availability(
    current_user: User = Depends(
        require_roles([
            UserRole.TAROT_READER,
            UserRole.SPIRITUAL_CONSULTANT,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    availability = await get_availability_for_professional(
        current_user.id, db
    )

    if availability is None:
        return {
            "status": "success",
            "professional_id": str(current_user.id),
            "is_online": False,
            "accepting_bookings": True,
            "supports_chat": True,
            "supports_voice": True,
            "supports_video": True,
        }

    return {
        "status": "success",
        "professional_id": str(current_user.id),
        **availability_to_dict(availability),
    }


# ===========================================================================
# UPDATE MY AVAILABILITY
# PUT /api/v1/consultation-hub/me/availability
# ===========================================================================

@router.put("/me/availability")
async def update_my_availability(
    payload: AvailabilityUpdate,
    current_user: User = Depends(
        require_roles([
            UserRole.TAROT_READER,
            UserRole.SPIRITUAL_CONSULTANT,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    availability = await get_availability_for_professional(
        current_user.id, db
    )

    if availability is None:
        availability = ProfessionalAvailability(
            professional_id=current_user.id
        )
        db.add(availability)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(availability, field, value)

    try:
        await db.commit()
        await db.refresh(availability)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update professional availability.",
        )

    return {
        "status": "success",
        "message": "Availability updated successfully.",
        "professional_id": str(current_user.id),
        **availability_to_dict(availability),
    }


# ===========================================================================
# CREATE FREE BOOKING
# POST /api/v1/consultation-hub/bookings
# ===========================================================================

@router.post("/bookings", status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate,
    current_user: User = Depends(
        require_roles([UserRole.USER])
    ),
    db: AsyncSession = Depends(get_db),
):
    scheduled_at = normalize_datetime(payload.scheduled_at)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if scheduled_at <= now:
        raise HTTPException(
            status_code=400,
            detail="Appointment must be scheduled in the future.",
        )

    if payload.professional_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot book yourself.",
        )

    # Lock the professional row so simultaneous booking requests
    # for this professional are serialized until transaction completion.
    result = await db.execute(
        select(User)
        .where(User.id == payload.professional_id)
        .with_for_update()
    )
    professional = result.scalar_one_or_none()

    if professional is None:
        raise HTTPException(
            status_code=404,
            detail="Professional not found.",
        )

    if professional.role not in PROFESSIONAL_ROLES:
        raise HTTPException(
            status_code=400,
            detail="The selected account is not a consultation professional.",
        )

    availability = await get_availability_for_professional(
        professional.id, db
    )

    if availability is None or not availability.accepting_bookings:
        raise HTTPException(
            status_code=409,
            detail="This professional is not accepting bookings.",
        )

    if not availability.is_online:
        raise HTTPException(
            status_code=409,
            detail="This professional is currently offline.",
        )

    supported_modes = {
        "CHAT": availability.supports_chat,
        "VOICE": availability.supports_voice,
        "VIDEO": availability.supports_video,
    }

    if not supported_modes[payload.consultation_mode]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{payload.consultation_mode} consultations "
                "are not enabled for this professional."
            ),
        )

    requested_end = scheduled_at + timedelta(
        minutes=payload.duration_minutes
    )

    # An overlap exists when an existing appointment starts before
    # the requested appointment ends and ends after it starts.
    conflict_result = await db.execute(
        text("""
            SELECT id
            FROM consultation_bookings
            WHERE professional_id = :professional_id
              AND status IN ('PENDING', 'CONFIRMED')
              AND scheduled_at < :requested_end
              AND scheduled_at
                  + duration_minutes * INTERVAL '1 minute'
                  > :scheduled_at
            FOR UPDATE
        """),
        {
            "professional_id": professional.id,
            "requested_end": requested_end,
            "scheduled_at": scheduled_at,
        },
    )

    if conflict_result.first() is not None:
        raise HTTPException(
            status_code=409,
            detail="This professional already has a booking at that time.",
        )

    booking = ConsultationBooking(
        client_id=current_user.id,
        professional_id=professional.id,
        professional_type=professional.role,
        consultation_mode=payload.consultation_mode,
        scheduled_at=scheduled_at,
        duration_minutes=payload.duration_minutes,
        status="PENDING",
        amount=0,
    )

    db.add(booking)

    try:
        await db.commit()
        await db.refresh(booking)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Booking could not be saved.",
        )

    return {
        "status": "success",
        "message": "Free consultation booking created.",
        "booking": booking_to_dict(booking),
    }


# ===========================================================================
# LIST MY BOOKINGS
# GET /api/v1/consultation-hub/bookings/me
# ===========================================================================

@router.get("/bookings/me")
async def list_my_bookings(
    current_user: User = Depends(
        require_roles([
            UserRole.USER,
            UserRole.TAROT_READER,
            UserRole.SPIRITUAL_CONSULTANT,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.USER.value:
        condition = ConsultationBooking.client_id == current_user.id
    else:
        condition = ConsultationBooking.professional_id == current_user.id

    result = await db.execute(
        select(ConsultationBooking)
        .where(condition)
        .order_by(ConsultationBooking.scheduled_at.desc())
    )

    bookings = result.scalars().all()

    return {
        "status": "success",
        "count": len(bookings),
        "bookings": [booking_to_dict(item) for item in bookings],
    }


# ===========================================================================
# GET BOOKING DETAILS
# GET /api/v1/consultation-hub/bookings/{booking_id}
# ===========================================================================

@router.get("/bookings/{booking_id}")
async def get_booking(
    booking_id: UUID,
    current_user: User = Depends(
        require_roles([
            UserRole.USER,
            UserRole.TAROT_READER,
            UserRole.SPIRITUAL_CONSULTANT,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConsultationBooking).where(
            ConsultationBooking.id == booking_id
        )
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found.",
        )

    if (
        booking.client_id != current_user.id
        and booking.professional_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to view this booking.",
        )

    return {
        "status": "success",
        "booking": booking_to_dict(booking),
    }



# ===========================================================================
# CANCEL BOOKING
# PATCH /api/v1/consultation-hub/bookings/{booking_id}/cancel
# ===========================================================================

@router.patch("/bookings/{booking_id}/cancel")
async def cancel_booking(
    booking_id: UUID,
    current_user: User = Depends(
        require_roles([
            UserRole.USER,
            UserRole.TAROT_READER,
            UserRole.SPIRITUAL_CONSULTANT,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConsultationBooking)
        .where(ConsultationBooking.id == booking_id)
        .with_for_update()
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found.",
        )

    if (
        booking.client_id != current_user.id
        and booking.professional_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to cancel this booking.",
        )

    if booking.status not in ACTIVE_BOOKING_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Booking cannot be cancelled from status {booking.status}.",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if booking.scheduled_at <= now:
        raise HTTPException(
            status_code=409,
            detail="A booking cannot be cancelled after its start time.",
        )

    booking.status = "CANCELLED"

    try:
        await db.commit()
        await db.refresh(booking)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Booking cancellation failed.",
        )

    return {
        "status": "success",
        "message": "Booking cancelled successfully.",
        "booking": booking_to_dict(booking),
    }


# ===========================================================================
# RESPOND TO BOOKING
# PATCH /api/v1/consultation-hub/bookings/{booking_id}/respond
# ===========================================================================

class BookingResponse(BaseModel):
    action: Literal["CONFIRMED", "REJECTED"]


@router.patch("/bookings/{booking_id}/respond")
async def respond_to_booking(
    booking_id: UUID,
    payload: BookingResponse,
    current_user: User = Depends(
        require_roles([
            UserRole.TAROT_READER,
            UserRole.SPIRITUAL_CONSULTANT,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConsultationBooking)
        .where(ConsultationBooking.id == booking_id)
        .with_for_update()
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found.",
        )

    # Only the professional assigned to this booking can respond.
    if booking.professional_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot manage another professional's booking.",
        )

    if booking.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Only pending bookings can be confirmed or rejected.",
        )

    # normalize_datetime returns a naive UTC datetime.
    scheduled_at = normalize_datetime(booking.scheduled_at)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if scheduled_at <= now:
        raise HTTPException(
            status_code=409,
            detail="Past bookings cannot be confirmed or rejected.",
        )

    booking.status = payload.action

    try:
        await db.commit()
        await db.refresh(booking)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update booking status.",
        )

    return {
        "status": "success",
        "message": f"Booking {payload.action.lower()} successfully.",
        "booking": booking_to_dict(booking),
    }

# ===========================================================================
# PRIVATE CONSULTATION CHAT
# ===========================================================================

class ConsultationChatConnectionManager:
    """Manage active WebSocket connections by booking ID."""

    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, booking_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(booking_id, set()).add(websocket)

    def disconnect(self, booking_id: str, websocket: WebSocket):
        booking_connections = self.connections.get(booking_id, set())
        booking_connections.discard(websocket)

        if not booking_connections:
            self.connections.pop(booking_id, None)

    async def broadcast(self, booking_id: str, payload: dict):
        for connection in list(self.connections.get(booking_id, set())):
            try:
                await connection.send_json(payload)
            except Exception:
                self.disconnect(booking_id, connection)


chat_manager = ConsultationChatConnectionManager()


async def get_chat_booking(
    booking_id: UUID,
    user_id: UUID,
    db: AsyncSession,
):
    """Verify booking ownership, status, and chat mode."""

    result = await db.execute(
        select(ConsultationBooking).where(
            ConsultationBooking.id == booking_id
        )
    )
    booking = result.scalar_one_or_none()

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if user_id not in (booking.client_id, booking.professional_id):
        raise HTTPException(
            status_code=403,
            detail="You are not a participant in this booking.",
        )

    if booking.status != "CONFIRMED":
        raise HTTPException(
            status_code=409,
            detail="Chat is available only for confirmed bookings.",
        )

    if booking.consultation_mode != "CHAT":
        raise HTTPException(
            status_code=409,
            detail="This booking is not a chat consultation.",
        )

    return booking


# ---------------------------------------------------------------------------
# GET SAVED CHAT HISTORY
# GET /api/v1/consultation-hub/bookings/{booking_id}/chat/messages
# ---------------------------------------------------------------------------

@router.get("/bookings/{booking_id}/chat/messages")
async def get_chat_messages(
    booking_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before_id: UUID | None = Query(default=None),
    current_user: User = Depends(
        require_roles([
            UserRole.USER,
            UserRole.TAROT_READER,
            UserRole.SPIRITUAL_CONSULTANT,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    await get_chat_booking(booking_id, current_user.id, db)

    query = select(ConsultationChatMessage).where(
        ConsultationChatMessage.booking_id == booking_id
    )

    if before_id is not None:
        cursor_result = await db.execute(
            select(ConsultationChatMessage).where(
                ConsultationChatMessage.id == before_id,
                ConsultationChatMessage.booking_id == booking_id,
            )
        )
        cursor_message = cursor_result.scalar_one_or_none()

        if cursor_message is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid message history cursor.",
            )

        query = query.where(
            ConsultationChatMessage.created_at
            < cursor_message.created_at
        )

    query = query.order_by(
        ConsultationChatMessage.created_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    messages = list(result.scalars().all())
    messages.reverse()

    return {
        "status": "success",
        "messages": [
            {
                "id": str(item.id),
                "booking_id": str(item.booking_id),
                "sender_id": str(item.sender_id),
                "message": item.message,
                "created_at": item.created_at.isoformat() + "Z",
            }
            for item in messages
        ],
    }


# ---------------------------------------------------------------------------
# REAL-TIME CHAT WEBSOCKET
# WS /api/v1/consultation-hub/bookings/{booking_id}/chat/ws?token=JWT
# ---------------------------------------------------------------------------

@router.websocket("/bookings/{booking_id}/chat/ws")
async def consultation_chat_websocket(
    websocket: WebSocket,
    booking_id: UUID,
):
    await websocket.accept()

    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=4401, reason="Authentication required.")
        return

    # Authenticate using the same JWT settings as the HTTP dependencies.
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        token_data = TokenPayload(**payload)

        if not token_data.sub:
            raise ValueError("Missing token subject.")

        user_id = UUID(token_data.sub)

    except (JWTError, ValueError, TypeError):
        await websocket.close(code=4401, reason="Invalid token.")
        return

    booking_key = str(booking_id)

    try:
        async with AsyncSessionLocal() as db:
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if user is None:
                await websocket.close(code=4401, reason="User not found.")
                return

            try:
                await get_chat_booking(booking_id, user.id, db)
            except HTTPException as exc:
                await websocket.close(
                    code=4403,
                    reason=exc.detail[:120],
                )
                return

        # Register only after the participant has been authorized.
        chat_manager.connections.setdefault(booking_key, set()).add(websocket)

        while True:
            message = (await websocket.receive_text()).strip()

            if not message:
                continue

            if len(message) > 2000:
                await websocket.send_json({
                    "type": "error",
                    "detail": "Messages cannot exceed 2000 characters.",
                })
                continue

            async with AsyncSessionLocal() as db:
                # Recheck status and access for every incoming message.
                try:
                    await get_chat_booking(booking_id, user_id, db)
                except HTTPException as exc:
                    await websocket.send_json({
                        "type": "error",
                        "detail": exc.detail,
                    })
                    await websocket.close(code=4403)
                    return

                chat_message = ConsultationChatMessage(
                    booking_id=booking_id,
                    sender_id=user_id,
                    message=message,
                )

                db.add(chat_message)
                await db.commit()
                await db.refresh(chat_message)

                outgoing = {
                    "type": "message",
                    "id": str(chat_message.id),
                    "booking_id": str(booking_id),
                    "sender_id": str(user_id),
                    "message": chat_message.message,
                    "created_at": (
                        chat_message.created_at.isoformat() + "Z"
                    ),
                }

            await chat_manager.broadcast(booking_key, outgoing)

    except WebSocketDisconnect:
        pass
    finally:
        chat_manager.disconnect(booking_key, websocket)
