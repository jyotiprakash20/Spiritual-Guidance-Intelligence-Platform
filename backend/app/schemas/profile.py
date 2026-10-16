from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# -------------------------------------------------------------------
# PROFILE
# -------------------------------------------------------------------

class ProfileBase(BaseModel):
    full_name: Optional[str] = None
    age_group: Optional[str] = None
    interests: Optional[str] = None
    spiritual_goals: Optional[str] = None
    dynamic_persona: Optional[Dict[str, Any]] = None


class ProfileUpdate(ProfileBase):
    pass


class ProfileOut(ProfileBase):
    id: UUID
    user_id: UUID
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------
# USER PREFERENCES
# -------------------------------------------------------------------

class UserPreferencesUpdate(BaseModel):
    preferences: Dict[str, Any]


# -------------------------------------------------------------------
# COMPLETE USER PROFILE
# -------------------------------------------------------------------

class UserFullProfileOut(BaseModel):
    id: UUID
    email: str
    role: str
    preferences: Optional[Dict[str, Any]] = None
    profile: Optional[ProfileOut] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)