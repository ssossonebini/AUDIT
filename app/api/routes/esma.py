"""
ESMA European Common Enforcement Priorities API
"""
import logging
import re
import time
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import EsmaReport
from app.schemas.esma import EsmaReportSchema, EsmaReportListItem, EsmaCrawlStatus
from app.crawler import esma_scraper
from app.crawler import pdf_parser

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


@router.post("/reports/{report_id_or_int}/summarize")
def summarize_report(report_id_or_int: str, db: Session = Depends(get_db)):
    """PDF 내용을 Claude AI로 요약 (영문 → 한국어 구조화 분석)"""
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured.")

    if report_id_or_int.isdigit():
        report = db.query(EsmaReport).filter(EsmaReport.id == int(report_id_or_int)).first()
    else:
        report = db.query(EsmaReport).filter(EsmaReport.report_id == report_id_or_int).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    # raw_text 없으면 PDF 실시간 다운로드
    if not report.raw_text:
        if not report.pdf_url:
            raise HTTPException(status_code=404, detail="No PDF URL available for this report.")
        try:
            session = esma_scraper._session()
            path = esma_scraper.download_pdf(report.pdf_url, report.report_id, session)
            if not path:
                raise HTTPException(status_code=404, detail="PDF download failed. Please check the source URL directly.")
            raw_text = pdf_parser.extract_text(path)
            if not raw_text:
                raise HTTPException(status_code=422, detail="Could not extract text from PDF.")
            report.raw_text = raw_text[:50000]
            report.pdf_path = path
            db.commit()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error downloading PDF: {str(e)}")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    text = report.raw_text[:30000]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""The following is the content of an ESMA (European Securities and Markets Authority)
European Common Enforcement Priorities (ECEP) statement PDF.
Please summarize the key content in Korean using the following structure:

1. 전체 개요 (Overall Overview, 2-3 sentences)
2. 주요 중점심사 사항 목록 (Key Enforcement Priorities - each with a name and one-line description)
3. 기업 및 감사인에 대한 주요 시사점 (Key Implications for Companies / Auditors)

PDF Content:
{text}"""
            }
        ]
    )

    raw = message.content[0].text.strip()
    structured = _parse_esma_summary(raw)
    return {"summary": raw, "structured": structured}


def _parse_esma_summary(text: str) -> dict:
    """AI 마크다운 응답을 구조화된 dict로 변환"""
    lines = text.splitlines()
    overview_lines = []
    issues = []
    companies = []
    auditors = []
    section = None

    for line in lines:
        stripped = line.strip()

        if re.search(r"전체\s*개요|Overall\s*Overview", stripped, re.I):
            section = "overview"
            continue
        if re.search(r"주요\s*중점|중점심사\s*사항|Enforcement\s*Priorit|Key.*Focus|Key.*Issue", stripped, re.I):
            section = "issues"
            continue
        if re.search(r"기업.*시사점|감사인.*시사점|Implication|For\s*Compan|For\s*Auditor", stripped, re.I):
            section = "companies"
            continue
        if re.search(r"감사인.*대상|Auditor.*Implication", stripped, re.I):
            section = "auditors"
            continue
        if re.search(r"시사점", stripped, re.I) and section not in ("companies", "auditors"):
            section = "companies"
            continue

        if not stripped or re.match(r"^-{3,}$", stripped) or re.match(r"^#{1,4}\s", stripped):
            continue

        if section == "overview":
            overview_lines.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped))

        elif section == "issues":
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]
                if len(cells) >= 2 and not re.match(r"^[-:]+$", cells[0]):
                    title = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[0])
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[-1])
                    if not re.match(r"^(이슈|번호|No\.|Priority)", title, re.I):
                        issues.append({"number": len(issues) + 1, "title": title, "description": desc})
            else:
                m = re.match(
                    r"^[①②③④⑤⑥⑦⑧⑨⑩\-\*\d\.]+\s*\*?\*?([^*:：]+)\*?\*?[：:]\s*(.+)",
                    stripped
                )
                if m:
                    title = m.group(1).strip()
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", m.group(2).strip())
                    issues.append({"number": len(issues) + 1, "title": title, "description": desc})

        elif section in ("companies", "auditors"):
            target = companies if section == "companies" else auditors
            if stripped.startswith(("-", "•", "*")):
                item = re.sub(r"^[-•\*]\s*", "", stripped)
                item = re.sub(r"\*\*([^*]+)\*\*", r"\1", item)
                target.append(item)

    return {
        "overview": " ".join(overview_lines[:4]),
        "issues": issues,
        "implications": {"companies": companies, "auditors": auditors},
    }


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
                _crawl_state["processed"] += 1
                continue

            report = EsmaReport(
                report_id=report_id,
                title=meta["title"],
                pub_date=meta.get("pub_date"),
                year=meta.get("year"),
                url=meta.get("url", ""),
                pdf_url=meta.get("pdf_url", ""),
                category=meta.get("category", "ECEP"),
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
