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
