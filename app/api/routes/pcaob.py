"""
PCAOB Staff Publications API
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
from app.db.models import PcaobPublication
from app.schemas.pcaob import PcaobPublicationSchema, PcaobPublicationListItem, PcaobCrawlStatus
from app.crawler import pcaob_scraper
from app.crawler import pdf_parser

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


@router.post("/publications/{pub_id_or_int}/summarize")
def summarize_publication(pub_id_or_int: str, db: Session = Depends(get_db)):
    """PDF 내용을 Claude AI로 요약 (영문 PDF → 구조화된 분석 반환)"""
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured.")

    if pub_id_or_int.isdigit():
        pub = db.query(PcaobPublication).filter(PcaobPublication.id == int(pub_id_or_int)).first()
    else:
        pub = db.query(PcaobPublication).filter(PcaobPublication.pub_id == pub_id_or_int).first()

    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found.")

    # raw_text 없으면 PDF 실시간 다운로드
    if not pub.raw_text:
        if not pub.pdf_url:
            raise HTTPException(status_code=404, detail="No PDF URL available for this publication.")
        try:
            session = pcaob_scraper._session()
            path = pcaob_scraper.download_pdf(pub.pdf_url, pub.pub_id, session)
            if not path:
                raise HTTPException(status_code=404, detail="PDF download failed. Please check the source URL directly.")
            raw_text = pdf_parser.extract_text(path)
            if not raw_text:
                raise HTTPException(status_code=422, detail="Could not extract text from PDF.")
            pub.raw_text = raw_text[:50000]
            pub.pdf_path = path
            db.commit()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error downloading PDF: {str(e)}")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    text = pub.raw_text[:30000]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""The following is the content of a PCAOB (Public Company Accounting Oversight Board) staff publication PDF.
Please summarize the key content in the following structure (respond in Korean):

1. 전체 개요 (Overall Overview, 2-3 sentences)
2. 주요 감사 중점 사항 목록 (Key Inspection/Audit Focus Areas - each with a name and one-line description)
3. 감사인 및 기업에 대한 주요 시사점 (Key Implications for Auditors / Public Companies)

PDF Content:
{text}"""
            }
        ]
    )

    raw = message.content[0].text.strip()
    structured = _parse_pcaob_summary(raw)
    return {"summary": raw, "structured": structured}


def _parse_pcaob_summary(text: str) -> dict:
    """AI 마크다운 응답을 구조화된 dict로 변환 (PCAOB 영문 문서용)"""
    lines = text.splitlines()

    overview_lines = []
    issues = []
    companies = []
    auditors = []

    section = None

    for line in lines:
        stripped = line.strip()

        # 섹션 헤더 감지
        if re.search(r"전체\s*개요|Overall\s*Overview|Overview", stripped, re.I):
            section = "overview"
            continue
        if re.search(r"주요\s*감사\s*중점|Focus\s*Area|Inspection.*Priority|Audit.*Focus", stripped, re.I):
            section = "issues"
            continue
        if re.search(r"기업.*시사점|감사인.*시사점|Implications.*Auditor|Implications.*Compan|Public\s*Compan", stripped, re.I):
            section = "companies"
            continue
        if re.search(r"감사인.*대상|Auditor.*Implication|For\s*Auditor", stripped, re.I):
            section = "auditors"
            continue
        if re.search(r"시사점|Implication", stripped, re.I) and section not in ("companies", "auditors"):
            section = "companies"
            continue

        if not stripped or re.match(r"^-{3,}$", stripped) or re.match(r"^#{1,4}\s", stripped):
            continue

        if section == "overview":
            clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
            overview_lines.append(clean)

        elif section == "issues":
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]
                if len(cells) >= 2 and not re.match(r"^[-:]+$", cells[0]):
                    title = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[0])
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[-1])
                    if not re.match(r"^(이슈|번호|No\.|Focus|Area)", title, re.I):
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

    overview = " ".join(overview_lines[:4])
    return {
        "overview": overview,
        "issues": issues,
        "implications": {
            "companies": companies,
            "auditors": auditors,
        },
    }


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

            pub = PcaobPublication(
                pub_id=pub_id,
                title=meta["title"],
                pub_date=meta.get("pub_date"),
                year=meta.get("year"),
                url=meta.get("url", ""),
                pdf_url=meta.get("pdf_url", ""),
                category=meta.get("category", "Staff Publication"),
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
