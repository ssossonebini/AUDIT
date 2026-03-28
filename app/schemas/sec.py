from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SecSpeechListItem(BaseModel):
    id: int
    speech_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    url: str
    speaker: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None

    model_config = {"from_attributes": True}


class SecSpeechSchema(BaseModel):
    id: int
    speech_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    url: str
    speaker: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecCrawlStatus(BaseModel):
    status: str
    message: str
    total: int = 0
    processed: int = 0
