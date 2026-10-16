from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRole(str, Enum):
    USER = "User"
    TAROT_READER = "Tarot Reader"
    SPIRITUAL_CONSULTANT = "Spiritual Consultant"
    ADMIN = "Administrator"


class UserBase(BaseModel):
    email: EmailStr



class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User account password.",
    )

    role: UserRole = Field(
        default=UserRole.USER,
        description="Requested account role.",
    )



class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    preferences: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )