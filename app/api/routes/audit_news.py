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
from app.crawler import pdf_ingest

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


def _refetch_missing(db: Session) -> int:
    """본문(raw_text)이 비어 있는 기존 항목의 첨부 PDF를 다시 수집한다."""
    pending = (
        db.query(AuditNewsReport)
        .filter((AuditNewsReport.raw_text.is_(None)) | (AuditNewsReport.raw_text == ""))
        .all()
    )
    if not pending:
        return 0

    recovered = 0
    for rec in pending:
        _crawl_state["message"] = f"본문 재수집 중: {rec.title[:30]}..."
        raw_id = rec.ntt_id.replace("FSS-", "").replace("FSC-", "")
        try:
            if rec.source == "FSS":
                attachments = audit_news_scraper.fetch_fss_attachments(raw_id)
            else:
                attachments = audit_news_scraper.fetch_fsc_attachments(raw_id)

            path, text = pdf_ingest.ingest_first(
                attachments, audit_news_scraper.download_pdf, rec.ntt_id
            )
            if text:
                rec.pdf_path, rec.raw_text = path, text
                db.commit()
                recovered += 1
        except Exception as e:
            logger.warning(f"본문 재수집 실패 ({rec.ntt_id}): {e}")

    logger.info(f"본문 재수집: {len(pending)}건 중 {recovered}건 복구")
    return recovered


def _do_crawl(max_pages: int, db: Session):
    global _crawl_state
    _crawl_state = {
        "running": True, "total": 0, "processed": 0,
        "classified": 0, "message": "수집 준비 중...",
    }

    use_ai = bool(settings.ANTHROPIC_API_KEY)
    today  = date.today().isoformat()

    try:
        # ── 본문이 비어 있는 기존 항목 재수집 (자가 치유) ────
        # 증분 크롤링은 기존 ntt_id를 만나면 중단하므로, 이미 저장됐지만
        # 첨부 수집에 실패한 항목은 여기서 따로 다시 시도한다. AI 분류는
        # 이미 끝났으므로 재호출하지 않는다 (추가 비용 없음).
        _refetch_missing(db)

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

            # 첨부 PDF 수집 (분류 통과 항목만)
            _crawl_state["message"] = f"PDF 수집 중: {meta['title'][:35]}..."
            raw_id = meta["ntt_id"].replace("FSS-", "").replace("FSC-", "")
            try:
                if meta["source"] == "FSS":
                    attachments = audit_news_scraper.fetch_fss_attachments(raw_id)
                else:
                    attachments = audit_news_scraper.fetch_fsc_attachments(raw_id)
                pdf_path, raw_text = pdf_ingest.ingest_first(
                    attachments, audit_news_scraper.download_pdf, meta["ntt_id"]
                )
            except Exception as e:
                logger.warning(f"첨부 수집 실패 ({meta['ntt_id']}): {e}")
                pdf_path, raw_text = None, None

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
                pdf_path=pdf_path,
                raw_text=raw_text,
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
