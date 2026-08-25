from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CorpSearchResult(BaseModel):
    """DART 고유번호 검색 결과 — 등록 전에 어느 회사인지 고르는 용도."""
    corp_code: str
    corp_name: str
    stock_code: Optional[str] = None


class CompanyCreate(BaseModel):
    corp_code: str
    audit_year: int


class CompanyListItem(BaseModel):
    id: int
    corp_code: str
    corp_name: str
    stock_code: Optional[str] = None
    audit_year: Optional[int] = None
    workspace_path: Optional[str] = None
    has_financials: bool = False

    model_config = {"from_attributes": True}


class CompanySchema(CompanyListItem):
    industry_code: Optional[str] = None
    ceo_name: Optional[str] = None
    fiscal_month: Optional[str] = None
    created_at: datetime


class FinancialLine(BaseModel):
    sj_div: Optional[str] = None
    sj_nm: Optional[str] = None
    account_nm: Optional[str] = None
    account_detail: Optional[str] = None
    ord: Optional[int] = None
    currency: Optional[str] = None
    thstrm_nm: Optional[str] = None
    thstrm_amount: Optional[int] = None
    frmtrm_amount: Optional[int] = None
    bfefrmtrm_amount: Optional[int] = None

    model_config = {"from_attributes": True}


class FinancialsSummary(BaseModel):
    """수집 결과 요약 — 어느 판본을 몇 줄 받았는지."""
    bsns_year: int
    fs_div: str            # CFS=연결 / OFS=개별
    total_rows: int
    by_statement: dict[str, int]
    message: str
