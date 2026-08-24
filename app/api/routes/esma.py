"""
ESMA European Common Enforcement Priorities API
"""
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import EsmaReport
from app.schemas.esma import EsmaReportSchema, EsmaReportListItem, EsmaCrawlStatus
from app.crawler import esma_scraper
from app.crawler import pdf_parser
from app.crawler import pdf_ingest

logger = logging.getLogger(__name__)
router = APIRouter()

_crawl_state: dict = {"running": False, "total": 0, "processed": 0, "message": ""}


@router.get("/years", response_model=list[int])
def get_available_years(db: Session = Depends(get_db)):
    rows = db.query(EsmaReport.year).distinct().order_by(EsmaReport.year.desc()).all()
    return [r.year for r in rows if r.year]


@router.get("/reports", response_model=list[EsmaReportListItem])
def list_reports(year: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(EsmaReport)
    if year:
        q = q.filter(EsmaReport.year == year)
    return q.order_by(EsmaReport.pub_date.desc()).all()


@router.get("/reports/{report_id_or_int}", response_model=EsmaReportSchema)
def get_report(report_id_or_int: str, db: Session = Depends(get_db)):
    if report_id_or_int.isdigit():
        report = db.query(EsmaReport).filter(EsmaReport.id == int(report_id_or_int)).first()
    else:
        report = db.query(EsmaReport).filter(EsmaReport.report_id == report_id_or_int).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@router.post("/crawl", response_model=EsmaCrawlStatus)
def start_crawl(background_tasks: BackgroundTasks, max_items: int = 20, db: Session = Depends(get_db)):
    if _crawl_state["running"]:
        return EsmaCrawlStatus(
            status="running", message="Already crawling.",
            total=_crawl_state["total"], processed=_crawl_state["processed"],
        )
    background_tasks.add_task(_do_crawl, max_items, db)
    return EsmaCrawlStatus(status="started", message="Crawl started.")


@router.get("/crawl/status", response_model=EsmaCrawlStatus)
def crawl_status():
    if _crawl_state["running"]:
        return EsmaCrawlStatus(
            status="running", message=_crawl_state["message"],
            total=_crawl_state["total"], processed=_crawl_state["processed"],
        )
    return EsmaCrawlStatus(
        status="idle", message=_crawl_state.get("message", "Ready"),
        total=_crawl_state["total"], processed=_crawl_state["processed"],
    )


def _do_crawl(max_items: int, db: Session):
    global _crawl_state
    _crawl_state = {"running": True, "total": 0, "processed": 0, "message": "Fetching report list..."}

    try:
        reports = esma_scraper.fetch_report_list(max_items=max_items)
        _crawl_state["total"] = len(reports)
        _crawl_state["message"] = f"Found {len(reports)} reports"

        for meta in reports:
            report_id = meta["report_id"]
            _crawl_state["message"] = f"Processing: {meta['title'][:50]}..."

            existing = db.query(EsmaReport).filter(EsmaReport.report_id == report_id).first()
            if existing:
                # 본문이 비어 있으면 PDF 수집만 다시 시도한다 (자가 치유)
                if not existing.raw_text and (existing.pdf_url or meta.get("pdf_url")):
                    path, text = pdf_ingest.ingest(
                        esma_scraper.download_pdf,
                        existing.pdf_url or meta["pdf_url"],
                        report_id,
                        esma_scraper._session(),
                    )
                    if text:
                        existing.pdf_path, existing.raw_text = path, text
                        db.commit()
                        logger.info(f"본문 재수집 성공: {report_id}")
                _crawl_state["processed"] += 1
                continue

            pdf_url = meta.get("pdf_url", "")
            pdf_path, raw_text = pdf_ingest.ingest(
                esma_scraper.download_pdf, pdf_url, report_id, esma_scraper._session()
            ) if pdf_url else (None, None)

            report = EsmaReport(
                report_id=report_id,
                title=meta["title"],
                pub_date=meta.get("pub_date"),
                year=meta.get("year"),
                url=meta.get("url", ""),
                pdf_url=pdf_url,
                category=meta.get("category", "ECEP"),
                pdf_path=pdf_path,
                raw_text=raw_text,
            )
            db.add(report)
            db.commit()
            _crawl_state["processed"] += 1
            time.sleep(0.3)

        _crawl_state["message"] = f"Crawl complete: {_crawl_state['processed']} reports saved"

    except Exception as e:
        logger.exception("ESMA 크롤링 중 오류")
        _crawl_state["message"] = f"Error: {str(e)}"
    finally:
        _crawl_state["running"] = False
