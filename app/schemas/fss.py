from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AuditIssueSchema(BaseModel):
    id: int
    issue_number: int
    issue_title: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class FssArticleSchema(BaseModel):
    id: int
    ntt_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    url: str
    summary: Optional[str] = None
    issues: list[AuditIssueSchema] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class FssArticleListItem(BaseModel):
    id: int
    ntt_id: str
    title: str
    pub_date: Optional[str] = None
    year: Optional[int] = None
    url: str
    summary: Optional[str] = None
    issue_count: int = 0

    model_config = {"from_attributes": True}


class CrawlStatus(BaseModel):
    status: str
    message: str
    total: int = 0
    processed: int = 0
