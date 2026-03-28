"""
한국회계기준원(KASB) K-IFRS 제·개정 현황 API
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
from app.db.models import KasbStandard
from app.schemas.kasb import KasbStandardSchema, KasbStandardListItem, KasbCrawlStatus
from app.crawler import kasb_scraper
from app.crawler import pdf_parser

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


@router.post("/standards/{standard_id}/summarize")
def summarize_standard(standard_id: str, db: Session = Depends(get_db)):
    """Claude AI로 기준서 변경 내용 요약 (PDF 또는 description 기반)"""
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    if standard_id.isdigit():
        std = db.query(KasbStandard).filter(KasbStandard.id == int(standard_id)).first()
    else:
        std = db.query(KasbStandard).filter(KasbStandard.standard_id == standard_id).first()
    if not std:
        raise HTTPException(status_code=404, detail="기준서를 찾을 수 없습니다.")

    # raw_text 없으면 PDF 다운로드 시도
    if not std.raw_text and std.pdf_url:
        try:
            session = kasb_scraper._session()
            path = kasb_scraper.download_pdf(std.pdf_url, std.standard_id, session)
            if path:
                raw_text = pdf_parser.extract_text(path)
                if raw_text:
                    std.raw_text = raw_text[:50000]
                    std.pdf_path = path
                    db.commit()
        except Exception as e:
            logger.warning(f"PDF 다운로드 실패, description으로 대체: {e}")

    # raw_text 또는 description 사용
    content = std.raw_text[:30000] if std.raw_text else std.description or ""
    if not content:
        raise HTTPException(
            status_code=404,
            detail="요약할 내용이 없습니다. PDF URL이 있는 기준서를 이용하거나 KASB 원문을 직접 확인해주세요."
        )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""다음은 한국회계기준원(KASB)이 제정 또는 개정한 K-IFRS 기준서 관련 내용입니다.
기준서명: {std.standard_number} {std.standard_name}
개정유형: {std.amendment_type}
시행일: {std.effective_date}
{f'대체기준서: {std.replaced_standard}' if std.replaced_standard else ''}

아래 항목으로 핵심 내용을 한국어로 요약해주세요:

1. 전체 개요 (2-3문장: 무엇이 왜 바뀌었는지)
2. 주요 변경 사항 목록 (각 변경 사항과 한 줄 설명)
3. 기업 회계담당자 및 감사인에 대한 주요 시사점

내용:
{content}""",
            }
        ],
    )

    raw = message.content[0].text.strip()
    structured = _parse_kasb_summary(raw)
    return {"summary": raw, "structured": structured}


def _parse_kasb_summary(text: str) -> dict:
    lines = text.splitlines()
    overview_lines = []
    changes = []
    implications = []
    section = None

    for line in lines:
        stripped = line.strip()

        if re.search(r"전체\s*개요", stripped):
            section = "overview"
            continue
        if re.search(r"주요\s*변경|변경\s*사항", stripped):
            section = "changes"
            continue
        if re.search(r"시사점|주의사항|감사인|회계담당", stripped) and section != "implications":
            section = "implications"
            continue

        if not stripped or re.match(r"^-{3,}$", stripped) or re.match(r"^#{1,4}\s", stripped):
            continue

        if section == "overview":
            overview_lines.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped))

        elif section == "changes":
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]
                if len(cells) >= 2 and not re.match(r"^[-:]+$", cells[0]):
                    title = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[0])
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[-1])
                    changes.append({"number": len(changes) + 1, "title": title, "description": desc})
            else:
                m = re.match(
                    r"^[①②③④⑤⑥⑦⑧⑨⑩\-\*\d\.]+\s*\*?\*?([^*:：]+)\*?\*?[：:]\s*(.+)",
                    stripped,
                )
                if m:
                    changes.append({
                        "number": len(changes) + 1,
                        "title": m.group(1).strip(),
                        "description": re.sub(r"\*\*([^*]+)\*\*", r"\1", m.group(2).strip()),
                    })

        elif section == "implications":
            if stripped.startswith(("-", "•", "*")):
                item = re.sub(r"^[-•\*]\s*", "", stripped)
                implications.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", item))

    return {
        "overview": " ".join(overview_lines[:4]),
        "changes": changes,
        "implications": implications,
    }


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
                pdf_url=meta.get("pdf_url", ""),
                description=meta.get("description", ""),
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
