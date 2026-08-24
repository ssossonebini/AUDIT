from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AuditNewsListItem(BaseModel):
    id: int
    source: str
    ntt_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    department: Optional[str] = None
    url: Optional[str] = None
    ai_reason: Optional[str] = None
    summary: Optional[str] = None

    model_config = {"from_attributes": True}


class AuditNewsSchema(AuditNewsListItem):
    created_at: datetime
    has_raw_text: bool = False


class CrawlHistorySchema(BaseModel):
    source: str
    last_crawled_at: Optional[datetime] = None
    last_sdate: Optional[str] = None
    total_new_items: int = 0

    model_config = {"from_attributes": True}


class AuditNewsCrawlStatus(BaseModel):
    status: str
    message: str
    total: int = 0
    processed: int = 0
    classified: int = 0    # AI 분류 통과 건수
    fss_history: Optional[CrawlHistorySchema] = None
    fsc_history: Optional[CrawlHistorySchema] = None
