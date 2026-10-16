from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

class PalmFeatureDocument(BaseModel):
    reading_id: str
    image_url: str
    detected_lines: Dict[str, Any] = {}
    structural_metrics: Optional[Dict[str, Any]] = None
    confidence: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TarotDataDocument(BaseModel):
    reading_id: str
    spread_type: str
    cards_drawn: List[Dict[str, Any]]
    interpretation_synthesis: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class InsightDocument(BaseModel):
    user_id: str
    reading_id: Optional[str] = None
    category: str  # Career, Love, Spiritual, Health
    synthesis_text: str
    confidence_score: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)

class ReadingSessionDocument(BaseModel):
    user_id: str
    session_state: str  # IN_PROGRESS, COMPLETED, ABANDONED
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class NotificationDocument(BaseModel):
    user_id: str
    title: str
    message: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class LogDocument(BaseModel):
    level: str  # INFO, WARNING, ERROR
    endpoint: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)