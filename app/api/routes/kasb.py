"""
한국회계기준원(KASB) K-IFRS 제·개정 현황 API
"""
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import KasbStandard
from app.schemas.kasb import KasbStandardSchema, KasbStandardListItem, KasbCrawlStatus
from app.crawler import kasb_scraper
from app.crawler import pdf_parser
from app.crawler import pdf_ingest

logger = logging.getLogger(__name__)
router = APIRouter()

_crawl_state: dict = {"running": False, "total": 0, "processed": 0, "message": ""}


@router.get("/effective-years", response_model=list[int])
def get_effective_years(db: Session = Depends(get_db)):
    """시행 연도 목록 반환"""
    rows = (
        db.query(KasbStandard.effective_year)
        .distinct()
        .order_by(KasbStandard.effective_year.asc())
        .all()
    )
    return [r.effective_year for r in rows if r.effective_year]


@router.get("/standards", response_model=list[KasbStandardListItem])
def list_standards(
    effective_year: Optional[int] = None,
    amendment_type: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """기준서 목록 조회 (시행연도·개정유형·카테고리 필터 가능)"""
    q = db.query(KasbStandard)
    if effective_year:
        q = q.filter(KasbStandard.effective_year == effective_year)
    if amendment_type:
        q = q.filter(KasbStandard.amendment_type == amendment_type)
    if category:
        q = q.filter(KasbStandard.category == category)
    return q.order_by(KasbStandard.effective_year.asc(), KasbStandard.issued_date.desc()).all()


@router.get("/standards/{standard_id}", response_model=KasbStandardSchema)
def get_standard(standard_id: str, db: Session = Depends(get_db)):
    """기준서 상세 조회 (int ID 또는 standard_id slug)"""
    if standard_id.isdigit():
        std = db.query(KasbStandard).filter(KasbStandard.id == int(standard_id)).first()
    else:
        std = db.query(KasbStandard).filter(KasbStandard.standard_id == standard_id).first()
    if not std:
        raise HTTPException(status_code=404, detail="기준서를 찾을 수 없습니다.")
    return std


@router.post("/crawl", response_model=KasbCrawlStatus)
def start_crawl(
    background_tasks: BackgroundTasks,
    max_pages: int = 3,
    db: Session = Depends(get_db),
):
    if _crawl_state["running"]:
        return KasbCrawlStatus(
            status="running",
            message="이미 수집이 진행 중입니다.",
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    background_tasks.add_task(_do_crawl, max_pages, db)
    return KasbCrawlStatus(status="started", message="수집을 시작했습니다.")


@router.get("/crawl/status", response_model=KasbCrawlStatus)
def crawl_status():
    if _crawl_state["running"]:
        return KasbCrawlStatus(
            status="running",
            message=_crawl_state["message"],
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    return KasbCrawlStatus(
        status="idle",
        message=_crawl_state.get("message", "대기 중"),
        total=_crawl_state["total"],
        processed=_crawl_state["processed"],
    )


def _do_crawl(max_pages: int, db: Session):
    global _crawl_state
    _crawl_state = {"running": True, "total": 0, "processed": 0, "message": "기준서 목록 수집 중..."}

    try:
        standards = kasb_scraper.fetch_standard_list(max_pages=max_pages)
        _crawl_state["total"] = len(standards)
        _crawl_state["message"] = f"총 {len(standards)}개 기준서 발견"

        for meta in standards:
            sid = meta["standard_id"]
            _crawl_state["message"] = f"처리 중: {meta['standard_name'][:40]}..."

            existing = db.query(KasbStandard).filter(KasbStandard.standard_id == sid).first()
            if existing:
                _crawl_state["processed"] += 1
                continue

            pdf_url = meta.get("pdf_url", "")
            pdf_path, raw_text = pdf_ingest.ingest(
                kasb_scraper.download_pdf, pdf_url, sid, kasb_scraper._session()
            ) if pdf_url else (None, None)

            std = KasbStandard(
                standard_id=sid,
                standard_number=meta.get("standard_number", ""),
                standard_name=meta["standard_name"],
                amendment_type=meta.get("amendment_type", ""),
                category=meta.get("category", "K-IFRS"),
                issued_date=meta.get("issued_date", ""),
                effective_date=meta.get("effective_date", ""),
                effective_year=meta.get("effective_year"),
                early_adoption="Y" if meta.get("early_adoption") else "N",
                replaced_standard=meta.get("replaced_standard", ""),
                url=meta.get("url", ""),
                pdf_url=pdf_url,
                description=meta.get("description", ""),
                pdf_path=pdf_path,
                raw_text=raw_text,
            )
            db.add(std)
            db.commit()
            _crawl_state["processed"] += 1
            time.sleep(0.2)

        _crawl_state["message"] = f"수집 완료: {_crawl_state['processed']}개 기준서 저장"

    except Exception as e:
        logger.exception("KASB 수집 중 오류")
        _crawl_state["message"] = f"오류: {str(e)}"
    finally:
        _crawl_state["running"] = False
