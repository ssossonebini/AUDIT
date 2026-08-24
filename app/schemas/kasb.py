from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class KasbStandardSchema(BaseModel):
    id: int
    standard_id: str
    standard_number: Optional[str] = None
    standard_name: str
    amendment_type: Optional[str] = None
    category: Optional[str] = None
    issued_date: Optional[str] = None
    effective_date: Optional[str] = None
    effective_year: Optional[int] = None
    early_adoption: Optional[str] = None
    replaced_standard: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    has_raw_text: bool = False

    model_config = {"from_attributes": True}


class KasbStandardListItem(BaseModel):
    id: int
    standard_id: str
    standard_number: Optional[str] = None
    standard_name: str
    amendment_type: Optional[str] = None
    category: Optional[str] = None
    issued_date: Optional[str] = None
    effective_date: Optional[str] = None
    effective_year: Optional[int] = None
    early_adoption: Optional[str] = None
    replaced_standard: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None

    model_config = {"from_attributes": True}


class KasbCrawlStatus(BaseModel):
    status: str
    message: str
    total: int = 0
    processed: int = 0
