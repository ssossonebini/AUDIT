"""
PCAOB Staff Publications API
"""
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import PcaobPublication
from app.schemas.pcaob import PcaobPublicationSchema, PcaobPublicationListItem, PcaobCrawlStatus
from app.crawler import pcaob_scraper
from app.crawler import pdf_parser
from app.crawler import pdf_ingest

logger = logging.getLogger(__name__)
router = APIRouter()

_crawl_state: dict = {"running": False, "total": 0, "processed": 0, "message": ""}


@router.get("/years", response_model=list[int])
def get_available_years(db: Session = Depends(get_db)):
    """데이터가 있는 연도 목록 반환"""
    rows = db.query(PcaobPublication.year).distinct().order_by(PcaobPublication.year.desc()).all()
    return [r.year for r in rows if r.year]


@router.get("/publications", response_model=list[PcaobPublicationListItem])
def list_publications(year: Optional[int] = None, category: Optional[str] = None, db: Session = Depends(get_db)):
    """게시물 목록 조회 (연도/카테고리 필터 가능)"""
    q = db.query(PcaobPublication)
    if year:
        q = q.filter(PcaobPublication.year == year)
    if category:
        q = q.filter(PcaobPublication.category == category)
    return q.order_by(PcaobPublication.pub_date.desc()).all()


@router.get("/publications/{pub_id_or_int}", response_model=PcaobPublicationSchema)
def get_publication(pub_id_or_int: str, db: Session = Depends(get_db)):
    """게시물 상세 조회 (숫자 id 또는 pub_id slug)"""
    if pub_id_or_int.isdigit():
        pub = db.query(PcaobPublication).filter(PcaobPublication.id == int(pub_id_or_int)).first()
    else:
        pub = db.query(PcaobPublication).filter(PcaobPublication.pub_id == pub_id_or_int).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found.")
    return pub


@router.post("/crawl", response_model=PcaobCrawlStatus)
def start_crawl(background_tasks: BackgroundTasks, max_items: int = 30, db: Session = Depends(get_db)):
    """크롤링 시작 (백그라운드 작업)"""
    if _crawl_state["running"]:
        return PcaobCrawlStatus(
            status="running",
            message="Already crawling.",
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    background_tasks.add_task(_do_crawl, max_items, db)
    return PcaobCrawlStatus(status="started", message="Crawl started.")


@router.get("/crawl/status", response_model=PcaobCrawlStatus)
def crawl_status():
    """크롤링 진행 상태 조회"""
    if _crawl_state["running"]:
        return PcaobCrawlStatus(
            status="running",
            message=_crawl_state["message"],
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    return PcaobCrawlStatus(
        status="idle",
        message=_crawl_state.get("message", "Ready"),
        total=_crawl_state["total"],
        processed=_crawl_state["processed"],
    )


def _do_crawl(max_items: int, db: Session):
    """실제 크롤링 로직 (백그라운드 실행)"""
    global _crawl_state
    _crawl_state = {"running": True, "total": 0, "processed": 0, "message": "Fetching publication list..."}

    try:
        publications = pcaob_scraper.fetch_publication_list(max_items=max_items)
        _crawl_state["total"] = len(publications)
        _crawl_state["message"] = f"Found {len(publications)} publications"

        for meta in publications:
            pub_id = meta["pub_id"]
            _crawl_state["message"] = f"Processing: {meta['title'][:50]}..."

            existing = db.query(PcaobPublication).filter(PcaobPublication.pub_id == pub_id).first()
            if existing:
                _crawl_state["processed"] += 1
                continue

            pdf_url = meta.get("pdf_url", "")
            pdf_path, raw_text = pdf_ingest.ingest(
                pcaob_scraper.download_pdf, pdf_url, pub_id, pcaob_scraper._session()
            ) if pdf_url else (None, None)

            pub = PcaobPublication(
                pub_id=pub_id,
                title=meta["title"],
                pub_date=meta.get("pub_date"),
                year=meta.get("year"),
                url=meta.get("url", ""),
                pdf_url=pdf_url,
                category=meta.get("category", "Staff Publication"),
                pdf_path=pdf_path,
                raw_text=raw_text,
            )
            db.add(pub)
            db.commit()
            db.refresh(pub)

            _crawl_state["processed"] += 1
            time.sleep(0.3)

        _crawl_state["message"] = f"Crawl complete: {_crawl_state['processed']} publications saved"

    except Exception as e:
        logger.exception("PCAOB 크롤링 중 오류")
        _crawl_state["message"] = f"Error: {str(e)}"
    finally:
        _crawl_state["running"] = False
