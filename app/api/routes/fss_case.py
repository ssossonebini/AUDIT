"""
금융감독원 회계심사·감리 지적사례 API
"""
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import FssCaseReport
from app.schemas.fss_case import FssCaseReportSchema, FssCaseReportListItem, FssCaseCrawlStatus
from app.crawler import fss_case_scraper
from app.crawler import pdf_parser
from app.crawler import pdf_ingest

logger = logging.getLogger(__name__)
router = APIRouter()

_crawl_state: dict = {"running": False, "total": 0, "processed": 0, "message": ""}


@router.get("/years", response_model=list[int])
def get_available_years(db: Session = Depends(get_db)):
    """데이터가 있는 연도 목록 반환"""
    rows = db.query(FssCaseReport.year).distinct().order_by(FssCaseReport.year.desc()).all()
    return [r.year for r in rows if r.year]


@router.get("/cases", response_model=list[FssCaseReportListItem])
def list_cases(year: Optional[int] = None, db: Session = Depends(get_db)):
    """지적사례 목록 조회 (연도 필터 가능)"""
    q = db.query(FssCaseReport)
    if year:
        q = q.filter(FssCaseReport.year == year)
    return q.order_by(FssCaseReport.pub_date.desc()).all()


@router.get("/cases/{case_id}", response_model=FssCaseReportSchema)
def get_case(case_id: int, db: Session = Depends(get_db)):
    """지적사례 상세 조회"""
    case = db.query(FssCaseReport).filter(FssCaseReport.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="지적사례를 찾을 수 없습니다.")
    return case


@router.delete("/cases")
def reset_cases(db: Session = Depends(get_db)):
    """기존 지적사례 데이터 전체 삭제 (재수집 전 초기화용)"""
    count = db.query(FssCaseReport).count()
    db.query(FssCaseReport).delete()
    db.commit()
    return {"deleted": count, "message": f"{count}건 삭제 완료. 수집 시작 버튼으로 재수집하세요."}


@router.post("/crawl", response_model=FssCaseCrawlStatus)
def start_crawl(background_tasks: BackgroundTasks, max_pages: int = 5, db: Session = Depends(get_db)):
    """크롤링 시작 (백그라운드 작업)"""
    if _crawl_state["running"]:
        return FssCaseCrawlStatus(
            status="running",
            message="이미 크롤링이 진행 중입니다.",
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    background_tasks.add_task(_do_crawl, max_pages, db)
    return FssCaseCrawlStatus(status="started", message="크롤링을 시작했습니다.")


@router.get("/crawl/status", response_model=FssCaseCrawlStatus)
def crawl_status():
    """크롤링 진행 상태 조회"""
    if _crawl_state["running"]:
        return FssCaseCrawlStatus(
            status="running",
            message=_crawl_state["message"],
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    return FssCaseCrawlStatus(
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
        session = fss_case_scraper._session()

        cases_meta = fss_case_scraper.fetch_case_list(max_pages=max_pages)
        _crawl_state["total"] = len(cases_meta)
        _crawl_state["message"] = f"총 {len(cases_meta)}개 지적사례 게시글 발견"

        for meta in cases_meta:
            ntt_id = meta["ntt_id"]
            _crawl_state["message"] = f"처리 중: {meta['title'][:30]}..."

            existing = db.query(FssCaseReport).filter(FssCaseReport.ntt_id == ntt_id).first()
            if existing:
                _crawl_state["processed"] += 1
                continue

            # 상세 페이지에서 첨부파일 URL 추출
            detail = fss_case_scraper.fetch_case_detail(ntt_id, session)
            time.sleep(0.5)

            # PDF 다운로드 및 파싱 (HWP 첨부는 뒤로 미루고 매직바이트로 검증)
            pdf_path, raw_text = pdf_ingest.ingest_first(
                detail.get("attachments", []),
                fss_case_scraper.download_pdf,
                ntt_id,
                session,
            )

            case = FssCaseReport(
                ntt_id=ntt_id,
                title=meta["title"],
                pub_date=meta.get("pub_date"),
                year=meta.get("year"),
                period=meta.get("period", ""),
                url=meta["url"],
                pdf_path=pdf_path,
                raw_text=raw_text,
            )
            db.add(case)
            db.commit()
            _crawl_state["processed"] += 1

        _crawl_state["message"] = f"크롤링 완료: {_crawl_state['processed']}개 처리"

    except Exception as e:
        logger.exception("지적사례 크롤링 중 오류 발생")
        _crawl_state["message"] = f"오류: {str(e)}"
    finally:
        _crawl_state["running"] = False
