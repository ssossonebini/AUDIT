from sqlalchemy import (
    Boolean, Column, Integer, BigInteger, String, Text, DateTime, ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.database import Base


class FssArticle(Base):
    """금융감독원 보도자료 게시글"""
    __tablename__ = "fss_articles"

    id = Column(Integer, primary_key=True, index=True)
    ntt_id = Column(String, unique=True, index=True)  # 게시글 고유 ID
    title = Column(String, nullable=False)
    pub_date = Column(String)           # 게시일 (예: 2024-06-20)
    year = Column(Integer, index=True)  # 연도 (검색/필터용)
    url = Column(String)
    pdf_path = Column(String)           # 로컬 저장 PDF 경로
    raw_text = Column(Text)             # PDF 전체 텍스트
    summary = Column(Text)             # 요약 텍스트
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def has_raw_text(self) -> bool:
        """PDF 본문 수집 여부 (분석 가능 상태 표시용)"""
        return bool(self.raw_text)

    issues = relationship("AuditIssue", back_populates="article", cascade="all, delete-orphan")


class AuditIssue(Base):
    """중점심사 회계이슈 개별 항목"""
    __tablename__ = "audit_issues"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("fss_articles.id"))
    issue_number = Column(Integer)      # 이슈 번호 (1, 2, 3, 4)
    issue_title = Column(String)        # 이슈 제목
    description = Column(Text)         # 상세 내용

    article = relationship("FssArticle", back_populates="issues")


class PcaobPublication(Base):
    """PCAOB Staff Publications"""
    __tablename__ = "pcaob_publications"

    id = Column(Integer, primary_key=True, index=True)
    pub_id = Column(String, unique=True, index=True)   # 고유 slug
    title = Column(String, nullable=False)
    pub_date = Column(String)                          # 게시일 (예: 2024-12-09)
    year = Column(Integer, index=True)                 # 연도
    url = Column(String)                               # 게시물 페이지 URL
    pdf_url = Column(String)                           # 직접 PDF URL
    category = Column(String)                          # Spotlight / Staff Guidance 등
    pdf_path = Column(String)                          # 로컬 저장 경로
    raw_text = Column(Text)                            # PDF 전체 텍스트
    summary = Column(Text)                             # 요약 텍스트
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def has_raw_text(self) -> bool:
        """PDF 본문 수집 여부 (분석 가능 상태 표시용)"""
        return bool(self.raw_text)


class EsmaReport(Base):
    """ESMA European Common Enforcement Priorities (ECEP) 보고서"""
    __tablename__ = "esma_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, unique=True, index=True)  # 고유 slug (예: ecep-2024)
    title = Column(String, nullable=False)
    pub_date = Column(String)                            # 게시일 (예: 2024-10-28)
    year = Column(Integer, index=True)                   # 연도
    url = Column(String)                                 # ESMA 뉴스/문서 페이지 URL
    pdf_url = Column(String)                             # 직접 PDF URL
    category = Column(String)                            # ECEP / Enforcement Report 등
    pdf_path = Column(String)                            # 로컬 저장 경로
    raw_text = Column(Text)                              # PDF 전체 텍스트
    summary = Column(Text)                               # 요약 텍스트
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def has_raw_text(self) -> bool:
        """PDF 본문 수집 여부 (분석 가능 상태 표시용)"""
        return bool(self.raw_text)


class KasbStandard(Base):
    """한국회계기준원(KASB) K-IFRS 제·개정 기준서"""
    __tablename__ = "kasb_standards"

    id = Column(Integer, primary_key=True, index=True)
    standard_id = Column(String, unique=True, index=True)   # 고유 slug
    standard_number = Column(String)                        # 예: K-IFRS 제1118호
    standard_name = Column(String, nullable=False)          # 기준서명
    amendment_type = Column(String)                         # 신규제정 / 개정 / 해석서
    category = Column(String)                               # K-IFRS / ISSB / 일반기업
    issued_date = Column(String)                            # 공포(제정)일
    effective_date = Column(String)                         # 시행일
    effective_year = Column(Integer, index=True)            # 시행 연도 (필터용)
    early_adoption = Column(String)                         # 조기적용 가능 여부 ("Y"/"N")
    replaced_standard = Column(String)                      # 대체 기준서
    url = Column(String)                                    # KASB 페이지 URL
    pdf_url = Column(String)                                # 직접 PDF URL
    pdf_path = Column(String)                               # 로컬 저장 경로
    description = Column(Text)                              # 개요 설명
    raw_text = Column(Text)                                 # PDF 전체 텍스트
    summary = Column(Text)                                  # AI 요약 텍스트
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def has_raw_text(self) -> bool:
        """PDF 본문 수집 여부 (분석 가능 상태 표시용)"""
        return bool(self.raw_text)


class AuditNewsReport(Base):
    """FSS·FSC 보도자료 중 회계감사 관련 항목"""
    __tablename__ = "audit_news_reports"

    id         = Column(Integer, primary_key=True, index=True)
    source     = Column(String, index=True)          # "FSS" / "FSC"
    ntt_id     = Column(String, unique=True, index=True)  # "FSS-1234567" / "FSC-85959"
    title      = Column(String, nullable=False)
    pub_date   = Column(String)                      # 게시일 (예: 2025-03-15)
    year       = Column(Integer, index=True)         # 연도
    department = Column(String)                      # 담당부서
    url        = Column(String)                      # 원문 URL
    ai_reason  = Column(Text)                        # AI 분류 이유
    pdf_path   = Column(String)
    raw_text   = Column(Text)
    summary    = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def has_raw_text(self) -> bool:
        """PDF 본문 수집 여부 (분석 가능 상태 표시용)"""
        return bool(self.raw_text)


class CrawlHistory(Base):
    """증분 크롤링 이력 — 마지막 수집일 추적"""
    __tablename__ = "crawl_history"

    id               = Column(Integer, primary_key=True, index=True)
    source           = Column(String, unique=True, index=True)  # "FSS_NEWS" / "FSC_NEWS"
    last_crawled_at  = Column(DateTime)
    last_sdate       = Column(String)   # 마지막 수집 기준 시작일 (다음 크롤 시 sdate로 사용)
    total_new_items  = Column(Integer, default=0)


class FssCaseReport(Base):
    """금융감독원 회계심사·감리 지적사례 보도자료"""
    __tablename__ = "fss_case_reports"

    id = Column(Integer, primary_key=True, index=True)
    ntt_id = Column(String, unique=True, index=True)    # 게시글 고유 ID
    title = Column(String, nullable=False)
    pub_date = Column(String)                           # 게시일 (예: 2025-12-02)
    year = Column(Integer, index=True)                  # 연도
    period = Column(String)                             # 해당 지적사례 기간 (예: 2025년 상반기)
    url = Column(String)                                # 원문 URL
    pdf_path = Column(String)                           # 로컬 저장 PDF 경로
    raw_text = Column(Text)                             # PDF 전체 텍스트
    summary = Column(Text)                              # 요약 텍스트
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def has_raw_text(self) -> bool:
        """PDF 본문 수집 여부 (분석 가능 상태 표시용)"""
        return bool(self.raw_text)


class Company(Base):
    """분석 대상 회사. 등록 시 workspace 폴더가 함께 만들어진다."""
    __tablename__ = "companies"

    id             = Column(Integer, primary_key=True, index=True)
    corp_code      = Column(String, unique=True, index=True)  # DART 고유번호 8자리
    corp_name      = Column(String, nullable=False, index=True)
    stock_code     = Column(String)                  # 상장사만 존재
    industry_code  = Column(String)                  # 표준산업분류 (업종별 이슈 선별용)
    ceo_name       = Column(String)
    fiscal_month   = Column(String)                  # 결산월 (예: "12")
    audit_year     = Column(Integer, index=True)     # 감사 대상 연도
    workspace_path = Column(String)                  # workspace/{연도}_{회사명}
    created_at     = Column(DateTime, default=datetime.utcnow)

    statements = relationship(
        "FinancialStatement", back_populates="company", cascade="all, delete-orphan"
    )
    disclosures = relationship(
        "DisclosureItem", back_populates="company", cascade="all, delete-orphan"
    )
    filings = relationship(
        "DisclosureFiling", back_populates="company", cascade="all, delete-orphan"
    )
    news = relationship(
        "CompanyNews", back_populates="company", cascade="all, delete-orphan"
    )
    sections = relationship(
        "ReportSection", back_populates="company", cascade="all, delete-orphan"
    )

    @property
    def has_financials(self) -> bool:
        return bool(self.statements)

    @property
    def has_disclosures(self) -> bool:
        return bool(self.disclosures)

    @property
    def has_filings(self) -> bool:
        return bool(self.filings)

    @property
    def has_news(self) -> bool:
        return bool(self.news)

    @property
    def has_sections(self) -> bool:
        return bool(self.sections)


class FinancialStatement(Base):
    """재무제표 계정 한 줄. 사업보고서 한 건이 3개년 금액을 함께 담는다."""
    __tablename__ = "financial_statements"

    id         = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)

    bsns_year  = Column(Integer, index=True)   # 사업연도 (당기 기준)
    reprt_code = Column(String)                # 11011=사업보고서
    fs_div     = Column(String)                # CFS=연결 / OFS=개별
    sj_div     = Column(String, index=True)    # BS/IS/CIS/CF/SCE
    sj_nm      = Column(String)                # 재무제표명

    account_id     = Column(String)            # IFRS 계정 ID (표준계정이 아니면 -표준계정미사용-)
    account_nm     = Column(String)            # 계정명
    account_detail = Column(String)            # 자본변동표에만 존재
    ord            = Column(Integer)           # 표시 순서
    currency       = Column(String)

    thstrm_nm        = Column(String)          # 당기명 (예: 제 56 기)
    thstrm_amount    = Column(BigInteger)      # 당기
    frmtrm_amount    = Column(BigInteger)      # 전기
    bfefrmtrm_amount = Column(BigInteger)      # 전전기 — 사업보고서에만 존재

    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="statements")


class DisclosureItem(Base):
    """정기보고서 주요정보 한 행.

    배당·증자·자기주식·타법인출자·최대주주·감사의견은 응답 스키마가 제각각이라
    항목별 테이블 대신 payload(JSON)로 보관한다. 분석은 Claude Code 가
    payload 를 읽어 수행하므로 타입을 고정할 실익이 없다.
    """
    __tablename__ = "disclosure_items"

    id         = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)

    category   = Column(String, index=True)   # 배당 / 증자 / 자기주식 / 감사의견 ...
    api_file   = Column(String)               # 어느 엔드포인트에서 왔는지
    bsns_year  = Column(Integer, index=True)  # 사업연도
    reprt_code = Column(String)               # 11011=사업보고서
    rcept_no   = Column(String)               # 접수번호 (DART 원문 링크용)
    payload    = Column(Text)                 # 응답 행 원본 (JSON 문자열)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="disclosures")


class DisclosureFiling(Base):
    """공시 목록 한 건 (DS001 list.json).

    정기보고서 주요정보(disclosure_items)가 사업보고서 시점의 '현황'이라면,
    이쪽은 기중에 수시로 제출된 '이벤트'다. 자기주식취득결정·합병결정·
    대규모내부거래처럼 감사 대상 기간에 실제로 벌어진 일이 여기 잡힌다.
    """
    __tablename__ = "disclosure_filings"

    id         = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)

    rcept_no   = Column(String, index=True)   # 접수번호 — DART 원문 주소에 쓴다
    report_nm  = Column(String)               # 보고서명
    flr_nm     = Column(String)               # 제출인
    rcept_dt   = Column(String, index=True)   # 접수일자 YYYYMMDD
    pblntf_ty  = Column(String, index=True)   # A~J 공시유형
    tag        = Column(String, index=True)   # 감사 시사점 (자본거래·사업결합 …)
    rm         = Column(String)               # 비고 (유/정/공 등)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="filings")

    @property
    def dart_url(self) -> str:
        return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={self.rcept_no}"


class CompanyNews(Base):
    """회사 관련 뉴스 한 건 (Google News RSS).

    감사 어서션과 이어지도록 4분류로 태깅한다 — 산업·업황 / 재무·실적 /
    사업구조 변동 / 리스크. 분류에 걸리지 않은 기사도 버리지 않고 남긴다.
    """
    __tablename__ = "company_news"

    id           = Column(Integer, primary_key=True, index=True)
    company_id   = Column(Integer, ForeignKey("companies.id"), index=True)

    title        = Column(String, nullable=False)
    url          = Column(String)
    source       = Column(String)                 # 언론사
    published_at = Column(String, index=True)     # YYYY-MM-DD
    tag          = Column(String, index=True)     # 4분류, 미분류면 None
    ai_reason    = Column(Text)                   # 분류 근거 한 줄
    query        = Column(String)                 # 어느 질의로 걸렸는지
    created_at   = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="news")


class ReportSection(Base):
    """사업보고서 원문의 목차 한 구간.

    document.xml 은 본문만 8MB가 넘어 통째로 두면 읽을 수 없다. 목차 단위로
    쪼개 두고, 분석 때 필요한 구간만 골라 읽는다 (기준서 스킬과 같은 방식).

    주석은 SECTION-3 으로 내려가지 않고 SECTION-2 안의 TABLE-GROUP 에 하나씩
    들어 있다. level 3 은 그 TITLE 들을 가리킨다.

    전기말 사업보고서와 당기중 최신 분·반기보고서를 함께 담으므로, 어느
    보고서에서 온 구간인지는 reprt_code 로 가른다.
    """
    __tablename__ = "report_sections"

    id         = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)

    rcept_no   = Column(String, index=True)   # 어느 보고서에서 왔는지
    doc_label  = Column(String)               # 본문 / 감사보고서 / 검토보고서 …
    bsns_year  = Column(Integer, index=True)
    reprt_code = Column(String, index=True)   # 11011 사업 / 11012 반기 / 11013·11014 분기
    report_nm  = Column(String)               # 사업보고서 (2025.12)

    level      = Column(Integer, index=True)  # 1 대분류 / 2 중분류 / 3 주석 등
    title      = Column(String, index=True)
    parent     = Column(String)
    section_no = Column(String)               # AASSOCNOTE (D-0-3-1-0)

    body       = Column(Text)
    chars      = Column(Integer)
    audit_relevant = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="sections")

    @property
    def report_label(self) -> str:
        """화면에 쓸 보고서 이름. 옛 행은 reprt_code 가 비어 있다."""
        from app.crawler.dart_client import REPRT_LABELS
        return REPRT_LABELS.get(self.reprt_code or "", "사업보고서")
