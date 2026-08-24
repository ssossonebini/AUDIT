"""
금융감독원 중점심사 회계이슈 API
"""
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import FssArticle, AuditIssue
from app.schemas.fss import FssArticleSchema, FssArticleListItem, CrawlStatus
from app.crawler import fss_scraper
from app.crawler import pdf_parser
from app.crawler import pdf_ingest

logger = logging.getLogger(__name__)
router = APIRouter()

# 크롤링 상태 (간이 상태 저장)
_crawl_state: dict = {"running": False, "total": 0, "processed": 0, "message": ""}


@router.get("/years", response_model=list[int])
def get_available_years(db: Session = Depends(get_db)):
    """데이터가 있는 연도 목록 반환"""
    rows = db.query(FssArticle.year).distinct().order_by(FssArticle.year.desc()).all()
    return [r.year for r in rows if r.year]


@router.get("/articles", response_model=list[FssArticleListItem])
def list_articles(year: Optional[int] = None, db: Session = Depends(get_db)):
    """보도자료 목록 조회 (연도 필터 가능)"""
    q = db.query(FssArticle)
    if year:
        q = q.filter(FssArticle.year == year)
    articles = q.order_by(FssArticle.pub_date.desc()).all()

    result = []
    for a in articles:
        result.append(
            FssArticleListItem(
                id=a.id,
                ntt_id=a.ntt_id,
                title=a.title,
                pub_date=a.pub_date,
                year=a.year,
                url=a.url,
                summary=a.summary,
                issue_count=len(a.issues),
            )
        )
    return result


@router.get("/articles/{article_id}", response_model=FssArticleSchema)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """보도자료 상세 조회"""
    article = db.query(FssArticle).filter(FssArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return article


@router.post("/crawl", response_model=CrawlStatus)
def start_crawl(background_tasks: BackgroundTasks, max_pages: int = 5, db: Session = Depends(get_db)):
    """크롤링 시작 (백그라운드 작업)"""
    if _crawl_state["running"]:
        return CrawlStatus(
            status="running",
            message="이미 크롤링이 진행 중입니다.",
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )

    background_tasks.add_task(_do_crawl, max_pages, db)
    return CrawlStatus(status="started", message="크롤링을 시작했습니다.")


@router.get("/crawl/status", response_model=CrawlStatus)
def crawl_status():
    """크롤링 진행 상태 조회"""
    if _crawl_state["running"]:
        return CrawlStatus(
            status="running",
            message=_crawl_state["message"],
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    return CrawlStatus(
        status="idle",
        message=_crawl_state.get("message", "대기 중"),
        total=_crawl_state["total"],
        processed=_crawl_state["processed"],
    )


def _do_crawl(max_pages: int, db: Session):
    """실제 크롤링 로직 (백그라운드 실행)"""
    global _crawl_state
    _crawl_state = {"running": True, "total": 0, "processed": 0, "message": "목록 수집 중..."}

    try:
        session = fss_scraper._session()

        # 1단계: 목록 수집
        articles_meta = fss_scraper.fetch_article_list(max_pages=max_pages)
        _crawl_state["total"] = len(articles_meta)
        _crawl_state["message"] = f"총 {len(articles_meta)}개 게시글 발견"

        for meta in articles_meta:
            ntt_id = meta["ntt_id"]
            _crawl_state["message"] = f"처리 중: {meta['title'][:30]}..."

            # 이미 DB에 있는 경우 건너뜀
            # 본문(raw_text)이 이 프로젝트의 자산이므로 그것을 기준으로 재처리를 판단한다.
            # 본문이 비어 있으면 첨부 수집을 다시 시도한다 (자가 치유).
            existing = db.query(FssArticle).filter(FssArticle.ntt_id == ntt_id).first()
            if existing and existing.raw_text:
                _crawl_state["processed"] += 1
                continue

            # 2단계: 상세 페이지에서 첨부파일 URL 추출
            detail = fss_scraper.fetch_article_detail(ntt_id, session)
            time.sleep(0.5)

            # 3단계: PDF 다운로드 및 파싱 (HWP 첨부는 뒤로 미루고 매직바이트로 검증)
            pdf_path, raw_text = pdf_ingest.ingest_first(
                detail.get("attachments", []),
                fss_scraper.download_pdf,
                ntt_id,
                session,
            )
            raw_text = raw_text or ""

            # 4단계: 이슈 파싱 및 요약
            issues_data = pdf_parser.parse_audit_issues(raw_text) if raw_text else []
            summary = pdf_parser.build_summary(raw_text, issues_data) if raw_text else ""

            # 5단계: DB 저장
            if existing:
                article = existing
            else:
                article = FssArticle(
                    ntt_id=ntt_id,
                    title=meta["title"],
                    pub_date=meta.get("pub_date"),
                    year=meta.get("year"),
                    url=meta["url"],
                )
                db.add(article)
                db.flush()

            # 재수집에 실패했다면 기존 레코드를 덮어쓰지 않는다.
            # (덮어쓰면 이미 확보한 이슈까지 지워질 수 있다)
            if raw_text or not existing:
                article.pdf_path = pdf_path
                article.raw_text = raw_text or None
                article.summary = summary

                # 기존 이슈 삭제 후 재등록
                db.query(AuditIssue).filter(AuditIssue.article_id == article.id).delete()
                for issue in issues_data:
                    db.add(AuditIssue(
                        article_id=article.id,
                        issue_number=issue["issue_number"],
                        issue_title=issue["issue_title"],
                        description=issue.get("description"),
                    ))
            else:
                logger.warning(f"본문 재수집 실패 — 기존 데이터 유지: {ntt_id}")

            db.commit()
            _crawl_state["processed"] += 1

        _crawl_state["message"] = f"크롤링 완료: {_crawl_state['processed']}개 처리"

    except Exception as e:
        logger.exception("크롤링 중 오류 발생")
        _crawl_state["message"] = f"오류: {str(e)}"
    finally:
        _crawl_state["running"] = False
