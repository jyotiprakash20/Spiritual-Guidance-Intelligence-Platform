

import uuid

from datetime import datetime
from sqlalchemy import Boolean



from sqlalchemy import (

    Column,

    String,

    Text,

    Numeric,
    Integer,

    DateTime,

    ForeignKey,

    UniqueConstraint,

)

from sqlalchemy.dialects.postgresql import UUID, JSONB

from sqlalchemy.orm import relationship



from app.core.database import Base





class User(Base):

    __tablename__ = "users"



    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email = Column(String(255), unique=True, nullable=False, index=True)

    password_hash = Column(String(255), nullable=False)

    role = Column(String(50), default="User", nullable=False)

    approval_status = Column(
    String(20),
    nullable=False,
    default="APPROVED",
    server_default="APPROVED",
)

    preferences = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)



    # User profile

    profile = relationship(

        "Profile",

        back_populates="user",

        uselist=False,

        cascade="all, delete-orphan",

    )



    # User readings

    readings = relationship(

        "Reading",

        back_populates="user",

        cascade="all, delete-orphan",

    )



    # User payments

    payments = relationship(

        "Payment",

        back_populates="user",

        cascade="all, delete-orphan",

    )



    # User reports

    reports = relationship(

        "Report",

        back_populates="user",

        cascade="all, delete-orphan",

    )



    # Tarot Reader ↔ Client relationships

    reader_clients = relationship(

        "TarotReaderClient",

        foreign_keys="TarotReaderClient.reader_id",

        back_populates="reader",

        cascade="all, delete-orphan",

    )



    client_assignments = relationship(

        "TarotReaderClient",

        foreign_keys="TarotReaderClient.client_id",

        back_populates="client",

        cascade="all, delete-orphan",

    )



    # Spiritual Consultant ↔ Client relationships

    consultant_clients = relationship(

        "SpiritualConsultantClient",

        foreign_keys="SpiritualConsultantClient.consultant_id",

        back_populates="consultant",

        cascade="all, delete-orphan",

    )



    consultant_assignments = relationship(

        "SpiritualConsultantClient",

        foreign_keys="SpiritualConsultantClient.client_id",

        back_populates="client",

        cascade="all, delete-orphan",

    )



    # Consultation notes authored by this consultant

    consultation_notes = relationship(

        "ConsultationNote",

        foreign_keys="ConsultationNote.consultant_id",

        back_populates="consultant",

        cascade="all, delete-orphan",

    )



    # Consultation notes associated with this client

    client_consultation_notes = relationship(

        "ConsultationNote",

        foreign_keys="ConsultationNote.client_id",

        back_populates="client",

        cascade="all, delete-orphan",

    )





class TarotReaderClient(Base):

    """Authorization relationship between a Tarot Reader and a client."""



    __tablename__ = "tarot_reader_clients"



    __table_args__ = (

        UniqueConstraint(

            "reader_id",

            "client_id",

            name="uq_tarot_reader_client",

        ),

    )



    id = Column(

        UUID(as_uuid=True),

        primary_key=True,

        default=uuid.uuid4,

    )



    reader_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

        index=True,

    )



    client_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

        index=True,

    )



    status = Column(String(30), default="ACTIVE", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)



    reader = relationship(

        "User",

        foreign_keys=[reader_id],

        back_populates="reader_clients",

    )



    client = relationship(

        "User",

        foreign_keys=[client_id],

        back_populates="client_assignments",

    )





class SpiritualConsultantClient(Base):

    """Authorization relationship between a Spiritual Consultant and a client."""



    __tablename__ = "spiritual_consultant_clients"



    __table_args__ = (

        UniqueConstraint(

            "consultant_id",

            "client_id",

            name="uq_spiritual_consultant_client",

        ),

    )



    id = Column(

        UUID(as_uuid=True),

        primary_key=True,

        default=uuid.uuid4,

    )



    consultant_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

        index=True,

    )



    client_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

        index=True,

    )



    status = Column(String(30), default="ACTIVE", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)



    consultant = relationship(

        "User",

        foreign_keys=[consultant_id],

        back_populates="consultant_clients",

    )



    client = relationship(

        "User",

        foreign_keys=[client_id],

        back_populates="consultant_assignments",

    )





class Profile(Base):

    __tablename__ = "profiles"



    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)



    user_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        unique=True,

        nullable=False,

    )



    full_name = Column(String(100), nullable=True)

    age_group = Column(String(20), nullable=True)

    interests = Column(Text, nullable=True)

    spiritual_goals = Column(Text, nullable=True)

    dynamic_persona = Column(JSONB, nullable=True)



    updated_at = Column(

        DateTime,

        default=datetime.utcnow,

        onupdate=datetime.utcnow,

    )



    user = relationship("User", back_populates="profile")





class Reading(Base):

    __tablename__ = "readings"



    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)



    user_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

    )



    reading_type = Column(String(50), nullable=False)



    overall_insight_score = Column(Numeric(5, 2), nullable=True)

    mongo_payload_id = Column(String(64), nullable=True)

    analysis_data = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)



    user = relationship("User", back_populates="readings")



    reports = relationship(

        "Report",

        back_populates="reading",

        cascade="all, delete-orphan",

    )





class Payment(Base):

    __tablename__ = "payments"



    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)



    user_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

    )



    amount = Column(Numeric(10, 2), nullable=False)

    currency = Column(String(10), default="USD")

    status = Column(String(50), nullable=False)

    payment_method = Column(String(50), nullable=True)

    transaction_id = Column(String(255), unique=True, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)



    user = relationship("User", back_populates="payments")





class Report(Base):

    __tablename__ = "reports"



    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)



    user_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

    )



    reading_id = Column(

        UUID(as_uuid=True),

        ForeignKey("readings.id", ondelete="CASCADE"),

        nullable=True,

    )



    report_title = Column(String(255), nullable=False)

    report_summary = Column(Text, nullable=True)

    actionable_steps = Column(JSONB, nullable=True)

    pdf_storage_url = Column(String(500), nullable=True)

    generated_at = Column(DateTime, default=datetime.utcnow)



    user = relationship("User", back_populates="reports")

    reading = relationship("Reading", back_populates="reports")





class ConsultationNote(Base):

    """

    Stores consultation notes and follow-up progress for an assigned client.

    """



    __tablename__ = "consultation_notes"



    id = Column(

        UUID(as_uuid=True),

        primary_key=True,

        default=uuid.uuid4,

    )



    consultant_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

        index=True,

    )



    client_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="CASCADE"),

        nullable=False,

        index=True,

    )



    reading_id = Column(

        UUID(as_uuid=True),

        ForeignKey("readings.id", ondelete="SET NULL"),

        nullable=True,

        index=True,

    )



    title = Column(String(200), nullable=False)

    session_notes = Column(Text, nullable=False)



    follow_up_actions = Column(

        JSONB,

        nullable=False,

        default=list,

    )



    progress_status = Column(

        String(30),

        nullable=False,

        default="IN_PROGRESS",

    )



    next_follow_up_at = Column(DateTime, nullable=True)



    created_at = Column(

        DateTime,

        nullable=False,

        default=datetime.utcnow,

    )



    updated_at = Column(

        DateTime,

        nullable=False,

        default=datetime.utcnow,

        onupdate=datetime.utcnow,

    )



    consultant = relationship(

        "User",

        foreign_keys=[consultant_id],

        back_populates="consultation_notes",

    )



    client = relationship(

        "User",

        foreign_keys=[client_id],

        back_populates="client_consultation_notes",

    )



    reading = relationship(

        "Reading",

        foreign_keys=[reading_id],

    )





class AdminActivityLog(Base):

    __tablename__ = "admin_activity_logs"



    id = Column(

        UUID(as_uuid=True),

        primary_key=True,

        default=uuid.uuid4,

    )



    admin_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="SET NULL"),

        nullable=True,

        index=True,

    )



    action = Column(String(100), nullable=False)



    target_user_id = Column(

        UUID(as_uuid=True),

        ForeignKey("users.id", ondelete="SET NULL"),

        nullable=True,

        index=True,

    )



    old_value = Column(String(255), nullable=True)

    new_value = Column(String(255), nullable=True)

    details = Column(JSONB, nullable=True)



    created_at = Column(

        DateTime,

        nullable=False,

        default=datetime.utcnow,

        index=True,

    )



class ConsultationFeedback(Base):
    """Client-submitted feedback about a consultant session or reading."""

    __tablename__ = "consultation_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consultant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reading_id = Column(
        UUID(as_uuid=True),
        ForeignKey("readings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    consultation_note_id = Column(
        UUID(as_uuid=True),
        ForeignKey("consultation_notes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rating = Column(Integer, nullable=False)
    comments = Column(Text, nullable=True)
    submitted_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    consultant = relationship("User", foreign_keys=[consultant_id])
    client = relationship("User", foreign_keys=[client_id])
    reading = relationship("Reading", foreign_keys=[reading_id])
    consultation_note = relationship(
        "ConsultationNote", foreign_keys=[consultation_note_id]
    )


class ConsultationOutcome(Base):
    """Recorded follow-up outcome; not proof that guidance caused the result."""

    __tablename__ = "consultation_outcomes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consultant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reading_id = Column(
        UUID(as_uuid=True),
        ForeignKey("readings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    consultation_note_id = Column(
        UUID(as_uuid=True),
        ForeignKey("consultation_notes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    outcome = Column(String(30), nullable=False)
    notes = Column(Text, nullable=True)
    recorded_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    consultant = relationship("User", foreign_keys=[consultant_id])
    client = relationship("User", foreign_keys=[client_id])
    reading = relationship("Reading", foreign_keys=[reading_id])
    consultation_note = relationship(
        "ConsultationNote", foreign_keys=[consultation_note_id]
    )


class ProfessionalAvailability(Base):
    __tablename__ = "professional_availability"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    professional_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    is_online = Column(Boolean, nullable=False, default=False)
    accepting_bookings = Column(Boolean, nullable=False, default=True)

    supports_chat = Column(Boolean, nullable=False, default=True)
    supports_voice = Column(Boolean, nullable=False, default=True)
    supports_video = Column(Boolean, nullable=False, default=True)

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

# ---------------------------------------------------------------------------
# CONSULTATION BOOKINGS
# ---------------------------------------------------------------------------

class ConsultationBooking(Base):
    """Free consultation appointments between users and professionals."""

    __tablename__ = "consultation_bookings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    professional_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    professional_type = Column(
        String(40),
        nullable=False,
    )

    consultation_mode = Column(
        String(20),
        nullable=False,
    )

    scheduled_at = Column(
        DateTime,
        nullable=False,
    )

    duration_minutes = Column(
        Integer,
        nullable=False,
        default=30,
    )

    status = Column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True,
    )

    amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    
class ConsultationChatMessage(Base):
    """Persistent messages exchanged within a confirmed chat booking."""

    __tablename__ = "consultation_chat_messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("consultation_bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    message = Column(Text, nullable=False)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
