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
    has_disclosures: bool = False

    model_config = {"from_attributes": True}


class CompanySchema(CompanyListItem):
    industry_code: Optional[str] = None
    ceo_name: Optional[str] = None
    fiscal_month: Optional[str] = None
    created_at: datetime


class FinancialLine(BaseModel):
    fs_div: Optional[str] = None
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


class FinancialsCollected(BaseModel):
    """재무제표 구분 하나의 수집 결과."""
    fs_div: str            # CFS=연결 / OFS=별도
    label: str             # "연결" / "별도"
    total_rows: int
    by_statement: dict[str, int]


class FinancialsSummary(BaseModel):
    """수집 결과 요약 — 연결·별도를 모두 받으므로 목록으로 돌려준다."""
    bsns_year: int
    collected: list[FinancialsCollected]
    message: str


class DisclosureLine(BaseModel):
    """주요정보 한 행. payload 는 API 응답 원본을 그대로 담는다."""
    id: int
    category: Optional[str] = None
    bsns_year: Optional[int] = None
    rcept_no: Optional[str] = None
    payload: dict = {}

    model_config = {"from_attributes": True}


class DisclosureCollected(BaseModel):
    category: str
    label: str
    rows: int
    years: list[int]
    error: Optional[str] = None    # 이 항목만 실패했을 때의 사유


class DisclosuresSummary(BaseModel):
    years: list[int]
    period: str                    # 사람이 읽는 수집기간 설명
    collected: list[DisclosureCollected]
    total_rows: int
    message: str
