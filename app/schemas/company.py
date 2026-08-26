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
    has_filings: bool = False
    has_news: bool = False

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


class FilingLine(BaseModel):
    """공시 목록 한 건."""
    id: int
    rcept_no: Optional[str] = None
    report_nm: Optional[str] = None
    flr_nm: Optional[str] = None
    rcept_dt: Optional[str] = None
    pblntf_ty: Optional[str] = None
    tag: Optional[str] = None
    rm: Optional[str] = None
    dart_url: Optional[str] = None

    model_config = {"from_attributes": True}


class FilingsSummary(BaseModel):
    period: str                      # 사람이 읽는 수집기간
    total_rows: int
    by_type: dict[str, int]          # 공시유형별 건수
    by_tag: dict[str, int]           # 감사 시사점별 건수
    untagged: int                    # 규칙에 걸리지 않은 건수
    message: str


class NewsLine(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    tag: Optional[str] = None
    ai_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class NewsSummary(BaseModel):
    period: str
    fetched: int                   # 잡음·중복 제거 후 후보 건수
    saved: int
    by_tag: dict[str, int]
    untagged: int
    ai_used: bool
    message: str


class ExportSummary(BaseModel):
    root: str
    files: list[str]
    chars: dict[str, int]
    approx_tokens: int          # 한국어 대략 1.7자 = 1토큰
    message: str
