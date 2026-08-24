from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FssCaseReportSchema(BaseModel):
    id: int
    ntt_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    period: Optional[str] = None
    url: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    has_raw_text: bool = False

    model_config = {"from_attributes": True}


class FssCaseReportListItem(BaseModel):
    id: int
    ntt_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    period: Optional[str] = None
    url: Optional[str] = None
    summary: Optional[str] = None

    model_config = {"from_attributes": True}


class FssCaseCrawlStatus(BaseModel):
    status: str
    message: str
    total: int = 0
    processed: int = 0
