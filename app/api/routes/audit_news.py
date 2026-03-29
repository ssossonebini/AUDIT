"""
FSS·FSC 보도자료 중 회계감사 관련 항목 API
- 증분 크롤링 (CrawlHistory 기반 sdate 자동 관리)
- 키워드 1차 필터 → Claude AI 2차 분류
"""
import json
import logging
import re
import time
from datetime import datetime, date
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import AuditNewsReport, CrawlHistory
from app.schemas.audit_news import (
    AuditNewsListItem, AuditNewsSchema,
    AuditNewsCrawlStatus, CrawlHistorySchema,
)
from app.crawler import audit_news_scraper, pdf_parser

logger = logging.getLogger(__name__)
router = APIRouter()

_crawl_state: dict = {
    "running": False, "total": 0, "processed": 0,
    "classified": 0, "message": "",
}

DEFAULT_START_DATE = "2025-01-01"


# ── 조회 ──────────────────────────────────────────────────────

@router.get("/years", response_model=list[int])
def get_years(db: Session = Depends(get_db)):
    rows = (
        db.query(AuditNewsReport.year)
        .distinct()
        .order_by(AuditNewsReport.year.desc())
        .all()
    )
    return [r.year for r in rows if r.year]


@router.get("/news", response_model=list[AuditNewsListItem])
def list_news(
    year: Optional[int] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(AuditNewsReport)
    if year:
        q = q.filter(AuditNewsReport.year == year)
    if source:
        q = q.filter(AuditNewsReport.source == source)
    return q.order_by(AuditNewsReport.pub_date.desc()).all()


@router.get("/news/{news_id}", response_model=AuditNewsSchema)
def get_news(news_id: int, db: Session = Depends(get_db)):
    item = db.query(AuditNewsReport).filter(AuditNewsReport.id == news_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    return item


@router.get("/history", response_model=list[CrawlHistorySchema])
def get_crawl_history(db: Session = Depends(get_db)):
    return db.query(CrawlHistory).all()


# ── AI 요약 ──────────────────────────────────────────────────

@router.post("/news/{news_id}/summarize")
def summarize_news(news_id: int, db: Session = Depends(get_db)):
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    item = db.query(AuditNewsReport).filter(AuditNewsReport.id == news_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

    if not item.raw_text:
        # PDF 실시간 다운로드 시도
        try:
            source = item.source
            raw_id = item.ntt_id.replace("FSS-", "").replace("FSC-", "")
            attachments = []
            if source == "FSS":
                attachments = audit_news_scraper.fetch_fss_attachments(raw_id)
            else:
                attachments = audit_news_scraper.fetch_fsc_attachments(raw_id)

            raw_text = ""
            for att in attachments:
                if ".pdf" in att["url"].lower() or "fileDown" in att["url"] or "atchFileId" in att["url"]:
                    path = audit_news_scraper.download_pdf(att["url"], item.ntt_id)
                    if path:
                        raw_text = pdf_parser.extract_text(path)
                        if raw_text:
                            item.pdf_path = path
                            break
                    time.sleep(0.5)

            if not raw_text:
                raise HTTPException(
                    status_code=404,
                    detail="PDF를 찾을 수 없습니다. 원문 보기에서 직접 확인해주세요."
                )
            item.raw_text = raw_text[:50000]
            db.commit()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF 다운로드 오류: {e}")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"""다음은 {item.source}({"금융감독원" if item.source == "FSS" else "금융위원회"})의 보도자료입니다.
회계감사·외부감사·감사보고서 관점에서 핵심 내용을 한국어로 요약해주세요.

1. 전체 개요 (2-3문장)
2. 회계감사에 영향을 주는 주요 변경·발표 사항 목록
3. 감사인 및 기업 회계담당자 시사점

제목: {item.title}
내용:
{item.raw_text[:30000]}""",
        }],
    )
    raw = message.content[0].text.strip()
    structured = _parse_summary(raw)
    return {"summary": raw, "structured": structured}


def _parse_summary(text: str) -> dict:
    lines = text.splitlines()
    overview_lines, changes, implications, section = [], [], [], None

    for line in lines:
        s = line.strip()
        if re.search(r"전체\s*개요", s):
            section = "overview"; continue
        if re.search(r"변경|발표\s*사항|주요.*사항", s):
            section = "changes"; continue
        if re.search(r"시사점", s) and section != "implications":
            section = "implications"; continue
        if not s or re.match(r"^-{3,}|^#{1,4}\s", s):
            continue

        if section == "overview":
            overview_lines.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", s))
        elif section == "changes":
            m = re.match(r"^[①-⑩\-\*\d\.]+\s*\*?\*?([^*:：]+)\*?\*?[：:]\s*(.+)", s)
            if m:
                changes.append({
                    "number": len(changes) + 1,
                    "title": m.group(1).strip(),
                    "description": re.sub(r"\*\*([^*]+)\*\*", r"\1", m.group(2).strip()),
                })
        elif section == "implications":
            if s.startswith(("-", "•", "*")):
                implications.append(re.sub(r"\*\*([^*]+)\*\*", r"\1",
                                           re.sub(r"^[-•*]\s*", "", s)))

    return {
        "overview": " ".join(overview_lines[:4]),
        "changes": changes,
        "implications": implications,
    }


# ── 크롤링 ────────────────────────────────────────────────────

@router.post("/crawl", response_model=AuditNewsCrawlStatus)
def start_crawl(
    background_tasks: BackgroundTasks,
    max_pages: int = 5,
    db: Session = Depends(get_db),
):
    if _crawl_state["running"]:
        return _running_status()
    background_tasks.add_task(_do_crawl, max_pages, db)
    return AuditNewsCrawlStatus(status="started", message="수집을 시작했습니다.")


@router.get("/crawl/status", response_model=AuditNewsCrawlStatus)
def crawl_status(db: Session = Depends(get_db)):
    fss_h = db.query(CrawlHistory).filter(CrawlHistory.source == "FSS_NEWS").first()
    fsc_h = db.query(CrawlHistory).filter(CrawlHistory.source == "FSC_NEWS").first()
    base = AuditNewsCrawlStatus(
        status="running" if _crawl_state["running"] else "idle",
        message=_crawl_state.get("message", "대기 중"),
        total=_crawl_state["total"],
        processed=_crawl_state["processed"],
        classified=_crawl_state["classified"],
        fss_history=CrawlHistorySchema.model_validate(fss_h) if fss_h else None,
        fsc_history=CrawlHistorySchema.model_validate(fsc_h) if fsc_h else None,
    )
    return base


@router.delete("/news")
def reset_news(db: Session = Depends(get_db)):
    count = db.query(AuditNewsReport).count()
    db.query(AuditNewsReport).delete()
    db.query(CrawlHistory).delete()
    db.commit()
    return {"deleted": count, "message": f"{count}건 삭제 및 수집 이력 초기화 완료."}


# ── 배경 크롤링 로직 ───────────────────────────────────────────

def _running_status():
    return AuditNewsCrawlStatus(
        status="running",
        message=_crawl_state["message"],
        total=_crawl_state["total"],
        processed=_crawl_state["processed"],
        classified=_crawl_state["classified"],
    )


def _get_sdate(db: Session, source_key: str) -> str:
    """마지막 수집일 조회. 없으면 DEFAULT_START_DATE 반환."""
    h = db.query(CrawlHistory).filter(CrawlHistory.source == source_key).first()
    if h and h.last_sdate:
        return h.last_sdate
    return DEFAULT_START_DATE


def _update_history(db: Session, source_key: str, new_count: int):
    today = date.today().isoformat()
    h = db.query(CrawlHistory).filter(CrawlHistory.source == source_key).first()
    if h:
        h.last_crawled_at = datetime.utcnow()
        h.last_sdate = today
        h.total_new_items = (h.total_new_items or 0) + new_count
    else:
        db.add(CrawlHistory(
            source=source_key,
            last_crawled_at=datetime.utcnow(),
            last_sdate=today,
            total_new_items=new_count,
        ))
    db.commit()


def _ai_classify(title: str, api_key: str) -> dict:
    """Claude Haiku로 회계감사 관련 여부 판단 (저비용)"""
    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{
                "role": "user",
                "content": (
                    "다음 금융당국 보도자료 제목이 기업의 회계처리, 외부감사, "
                    "또는 감사보고서에 직접적인 영향을 줄 수 있는지 판단하세요.\n\n"
                    f"제목: {title}\n\n"
                    '아래 JSON 형식으로만 답하세요:\n'
                    '{"relevant": true/false, "reason": "한 줄 이유"}'
                ),
            }],
        )
        return json.loads(msg.content[0].text.strip())
    except Exception as e:
        logger.warning(f"AI 분류 실패: {e}")
        return {"relevant": True, "reason": "AI 분류 실패 — 수동 확인 필요"}


def _do_crawl(max_pages: int, db: Session):
    global _crawl_state
    _crawl_state = {
        "running": True, "total": 0, "processed": 0,
        "classified": 0, "message": "수집 준비 중...",
    }

    use_ai = bool(settings.ANTHROPIC_API_KEY)
    today  = date.today().isoformat()

    try:
        # ── 기존 ntt_id 목록 (증분 중단 판단용) ──────────────
        existing_ids = {
            r.ntt_id for r in db.query(AuditNewsReport.ntt_id).all()
        }

        all_items = []

        # ── FSS 수집 ─────────────────────────────────────────
        fss_sdate = _get_sdate(db, "FSS_NEWS")
        _crawl_state["message"] = f"FSS 보도자료 수집 중... (기준일: {fss_sdate})"
        fss_items = audit_news_scraper.fetch_fss_news(
            sdate=fss_sdate, max_pages=max_pages, existing_ids=existing_ids
        )
        all_items.extend(fss_items)

        # ── FSC 수집 ─────────────────────────────────────────
        fsc_sdate = _get_sdate(db, "FSC_NEWS")
        _crawl_state["message"] = f"FSC 보도자료 수집 중... (기준일: {fsc_sdate})"
        fsc_items = audit_news_scraper.fetch_fsc_news(
            sdate=fsc_sdate, max_pages=max_pages, existing_ids=existing_ids
        )
        all_items.extend(fsc_items)

        _crawl_state["total"] = len(all_items)
        _crawl_state["message"] = (
            f"키워드 필터 통과: FSS {len(fss_items)}건 + FSC {len(fsc_items)}건"
        )

        fss_new = fsc_new = 0

        for meta in all_items:
            _crawl_state["message"] = f"AI 분류 중: {meta['title'][:35]}..."

            # AI 분류
            if use_ai:
                result = _ai_classify(meta["title"], settings.ANTHROPIC_API_KEY)
                if not result.get("relevant", True):
                    _crawl_state["processed"] += 1
                    continue
                ai_reason = result.get("reason", "")
            else:
                ai_reason = "AI 미설정 — 키워드 필터 통과 항목"

            # DB 저장
            report = AuditNewsReport(
                source=meta["source"],
                ntt_id=meta["ntt_id"],
                title=meta["title"],
                pub_date=meta.get("pub_date", ""),
                year=meta.get("year"),
                department=meta.get("department", ""),
                url=meta.get("url", ""),
                ai_reason=ai_reason,
            )
            db.add(report)
            db.commit()

            _crawl_state["classified"] += 1
            _crawl_state["processed"] += 1

            if meta["source"] == "FSS":
                fss_new += 1
            else:
                fsc_new += 1

            time.sleep(0.1)  # AI 호출 간 인터벌

        # ── CrawlHistory 업데이트 ──────────────────────────
        _update_history(db, "FSS_NEWS", fss_new)
        _update_history(db, "FSC_NEWS", fsc_new)

        _crawl_state["message"] = (
            f"완료 — 신규 저장: FSS {fss_new}건 / FSC {fsc_new}건 "
            f"(다음 수집 기준일: {today})"
        )

    except Exception as e:
        logger.exception("감사 보도자료 크롤링 오류")
        _crawl_state["message"] = f"오류: {e}"
    finally:
        _crawl_state["running"] = False
