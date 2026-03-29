from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
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
