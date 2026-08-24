from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EsmaReportListItem(BaseModel):
    id: int
    report_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    url: str
    pdf_url: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None

    model_config = {"from_attributes": True}


class EsmaReportSchema(BaseModel):
    id: int
    report_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    url: str
    pdf_url: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    has_raw_text: bool = False

    model_config = {"from_attributes": True}


class EsmaCrawlStatus(BaseModel):
    status: str
    message: str
    total: int = 0
    processed: int = 0
