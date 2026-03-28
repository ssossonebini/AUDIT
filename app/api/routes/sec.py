"""
SEC 회계·감사 연설문 / 성명서 API
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
from app.db.models import SecSpeech
from app.schemas.sec import SecSpeechSchema, SecSpeechListItem, SecCrawlStatus
from app.crawler import sec_scraper

logger = logging.getLogger(__name__)
router = APIRouter()

_crawl_state: dict = {"running": False, "total": 0, "processed": 0, "message": ""}


@router.get("/years", response_model=list[int])
def get_available_years(db: Session = Depends(get_db)):
    """데이터가 있는 연도 목록 반환"""
    rows = db.query(SecSpeech.year).distinct().order_by(SecSpeech.year.desc()).all()
    return [r.year for r in rows if r.year]


@router.get("/speeches", response_model=list[SecSpeechListItem])
def list_speeches(
    year: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """연설문 목록 조회"""
    q = db.query(SecSpeech)
    if year:
        q = q.filter(SecSpeech.year == year)
    if category:
        q = q.filter(SecSpeech.category == category)
    return q.order_by(SecSpeech.pub_date.desc()).all()


@router.get("/speeches/{speech_id_or_int}", response_model=SecSpeechSchema)
def get_speech(speech_id_or_int: str, db: Session = Depends(get_db)):
    """연설문 상세 조회"""
    if speech_id_or_int.isdigit():
        speech = db.query(SecSpeech).filter(SecSpeech.id == int(speech_id_or_int)).first()
    else:
        speech = db.query(SecSpeech).filter(SecSpeech.speech_id == speech_id_or_int).first()
    if not speech:
        raise HTTPException(status_code=404, detail="Speech not found.")
    return speech


@router.post("/speeches/{speech_id_or_int}/summarize")
def summarize_speech(speech_id_or_int: str, db: Session = Depends(get_db)):
    """연설문 본문을 Claude AI로 요약.
    raw_text 없으면 실시간으로 HTML 페이지에서 텍스트 추출.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured.")

    if speech_id_or_int.isdigit():
        speech = db.query(SecSpeech).filter(SecSpeech.id == int(speech_id_or_int)).first()
    else:
        speech = db.query(SecSpeech).filter(SecSpeech.speech_id == speech_id_or_int).first()

    if not speech:
        raise HTTPException(status_code=404, detail="Speech not found.")

    # raw_text 없으면 실시간 HTML 추출
    if not speech.raw_text:
        session = sec_scraper._session()
        text = sec_scraper.fetch_speech_text(speech.url, session)
        if not text:
            raise HTTPException(
                status_code=404,
                detail="Could not extract text from the speech page. Please view the source directly."
            )
        speech.raw_text = text[:60000]
        db.commit()

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    text = speech.raw_text[:30000]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""The following is the text of a speech or statement by the SEC (Securities and Exchange Commission)
Office of the Chief Accountant, related to accounting and auditing matters.
Please summarize the key content in Korean, using the following structure:

1. 전체 개요 (Overall Overview, 2-3 sentences)
2. 주요 회계·감사 이슈 목록 (Key Accounting/Auditing Issues - each with a name and one-line description)
3. 감사인 및 기업에 대한 주요 시사점 (Key Implications for Auditors / Public Companies)

Speech text:
{text}"""
            }
        ]
    )

    raw = message.content[0].text.strip()
    structured = _parse_sec_summary(raw)
    return {"summary": raw, "structured": structured}


def _parse_sec_summary(text: str) -> dict:
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
        if re.search(r"주요\s*회계|주요\s*감사|이슈\s*목록|Key.*Issue|Key.*Focus|Key.*Matter", stripped, re.I):
            section = "issues"
            continue
        if re.search(r"기업.*시사점|감사인.*시사점|Implication|For\s*Auditor|For\s*Compan", stripped, re.I):
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
            clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
            overview_lines.append(clean)

        elif section == "issues":
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]
                if len(cells) >= 2 and not re.match(r"^[-:]+$", cells[0]):
                    title = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[0])
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[-1])
                    if not re.match(r"^(이슈|번호|No\.|Issue)", title, re.I):
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


@router.post("/crawl", response_model=SecCrawlStatus)
def start_crawl(
    background_tasks: BackgroundTasks,
    max_items: int = 20,
    db: Session = Depends(get_db),
):
    """연설문 목록 수집 시작 (백그라운드 작업)"""
    if _crawl_state["running"]:
        return SecCrawlStatus(
            status="running",
            message="Already crawling.",
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    background_tasks.add_task(_do_crawl, max_items, db)
    return SecCrawlStatus(status="started", message="Crawl started.")


@router.get("/crawl/status", response_model=SecCrawlStatus)
def crawl_status():
    """크롤링 진행 상태 조회"""
    if _crawl_state["running"]:
        return SecCrawlStatus(
            status="running",
            message=_crawl_state["message"],
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    return SecCrawlStatus(
        status="idle",
        message=_crawl_state.get("message", "Ready"),
        total=_crawl_state["total"],
        processed=_crawl_state["processed"],
    )


def _do_crawl(max_items: int, db: Session):
    """실제 크롤링 로직 (백그라운드 실행)"""
    global _crawl_state
    _crawl_state = {"running": True, "total": 0, "processed": 0, "message": "Fetching speech list..."}

    try:
        speeches = sec_scraper.fetch_speech_list(max_items=max_items)
        _crawl_state["total"] = len(speeches)
        _crawl_state["message"] = f"Found {len(speeches)} speeches"

        session = sec_scraper._session()

        for meta in speeches:
            speech_id = meta["speech_id"]
            _crawl_state["message"] = f"Processing: {meta['title'][:50]}..."

            existing = db.query(SecSpeech).filter(SecSpeech.speech_id == speech_id).first()
            if existing:
                _crawl_state["processed"] += 1
                continue

            # HTML 본문 텍스트 실시간 추출
            raw_text = ""
            if meta.get("url"):
                raw_text = sec_scraper.fetch_speech_text(meta["url"], session)
                time.sleep(0.5)

            speech = SecSpeech(
                speech_id=speech_id,
                title=meta["title"],
                pub_date=meta.get("pub_date"),
                year=meta.get("year"),
                url=meta.get("url", ""),
                speaker=meta.get("speaker", ""),
                category=meta.get("category", "Staff Publication"),
                raw_text=raw_text[:60000] if raw_text else None,
            )
            db.add(speech)
            db.commit()
            _crawl_state["processed"] += 1

        _crawl_state["message"] = f"Crawl complete: {_crawl_state['processed']} speeches saved"

    except Exception as e:
        logger.exception("SEC 크롤링 중 오류")
        _crawl_state["message"] = f"Error: {str(e)}"
    finally:
        _crawl_state["running"] = False
