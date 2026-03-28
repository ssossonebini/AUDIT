"""
금융감독원 회계심사·감리 지적사례 API
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
from app.db.models import FssCaseReport
from app.schemas.fss_case import FssCaseReportSchema, FssCaseReportListItem, FssCaseCrawlStatus
from app.crawler import fss_case_scraper
from app.crawler import pdf_parser

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


@router.post("/cases/{case_id}/summarize")
def summarize_case(case_id: int, db: Session = Depends(get_db)):
    """PDF 내용을 Claude AI로 요약"""
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    case = db.query(FssCaseReport).filter(FssCaseReport.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="지적사례를 찾을 수 없습니다.")

    # raw_text 없으면 PDF 실시간 다운로드
    if not case.raw_text:
        try:
            session = fss_case_scraper._session()
            detail = fss_case_scraper.fetch_case_detail(case.ntt_id, session)
            raw_text = ""
            for attachment in detail.get("attachments", []):
                url = attachment["url"]
                if ".pdf" in url.lower() or "fileDown" in url or "atchFileId" in url:
                    path = fss_case_scraper.download_pdf(url, case.ntt_id, session)
                    if path:
                        raw_text = pdf_parser.extract_text(path)
                        if raw_text:
                            case.pdf_path = path
                            break
                    time.sleep(0.5)

            if not raw_text:
                # 현재 데이터가 가짜 nttId를 가진 시드 데이터일 수 있음
                # 사용자에게 재수집 안내
                hint = (
                    "PDF를 찾을 수 없습니다. "
                    "수집 패널의 [초기화 후 재수집] 버튼을 눌러 금감원 사이트에서 실제 데이터를 재수집해주세요. "
                    f"또는 원문 보기 링크에서 직접 확인하세요: {case.url or 'URL 없음'}"
                )
                raise HTTPException(status_code=404, detail=hint)
            case.raw_text = raw_text[:50000]
            db.commit()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF 다운로드 중 오류: {str(e)}")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    text = case.raw_text[:30000]
    period_info = f" ({case.period})" if case.period else ""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""다음은 금융감독원의 회계심사·감리 주요 지적사례{period_info} 보도자료 PDF 내용입니다.
아래 항목으로 핵심 내용을 한국어로 요약해주세요:

1. 전체 개요 (2-3문장, 몇 건의 지적사례를 다루는지, 주요 분야 포함)
2. 주요 지적사례 목록 (각 사례 유형과 한 줄 설명)
3. 기업 및 감사인에 대한 주요 시사점 (회계처리 시 주의사항)

PDF 내용:
{text}"""
            }
        ]
    )

    raw = message.content[0].text.strip()
    structured = _parse_case_summary(raw)
    return {"summary": raw, "structured": structured}


def _parse_case_summary(text: str) -> dict:
    """AI 마크다운 응답을 구조화된 dict로 변환"""
    lines = text.splitlines()
    overview_lines = []
    cases = []
    implications = []
    section = None

    for line in lines:
        stripped = line.strip()

        if re.search(r"전체\s*개요", stripped):
            section = "overview"
            continue
        if re.search(r"주요\s*지적사례\s*목록|지적사례\s*목록|지적\s*사례", stripped):
            section = "cases"
            continue
        if re.search(r"시사점|주의사항|기업.*감사인", stripped) and section not in ("implications",):
            section = "implications"
            continue

        if not stripped or re.match(r"^-{3,}$", stripped) or re.match(r"^#{1,4}\s", stripped):
            continue

        if section == "overview":
            overview_lines.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped))

        elif section == "cases":
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]
                if len(cells) >= 2 and not re.match(r"^[-:]+$", cells[0]):
                    title = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[0])
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[-1])
                    if not re.match(r"^(사례|순번|번호|No)", title):
                        cases.append({"number": len(cases) + 1, "title": title, "description": desc})
            else:
                m = re.match(
                    r"^[①②③④⑤⑥⑦⑧⑨⑩\-\*\d\.]+\s*\*?\*?([^*:：]+)\*?\*?[：:]\s*(.+)",
                    stripped
                )
                if m:
                    title = m.group(1).strip()
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", m.group(2).strip())
                    cases.append({"number": len(cases) + 1, "title": title, "description": desc})

        elif section == "implications":
            if stripped.startswith(("-", "•", "*")):
                item = re.sub(r"^[-•\*]\s*", "", stripped)
                item = re.sub(r"\*\*([^*]+)\*\*", r"\1", item)
                implications.append(item)

    return {
        "overview": " ".join(overview_lines[:4]),
        "cases": cases,
        "implications": implications,
    }


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

            pdf_path = None
            raw_text = ""

            # PDF 다운로드 및 파싱
            for attachment in detail.get("attachments", []):
                url = attachment["url"]
                if ".pdf" in url.lower() or "fileDown" in url or "atchFileId" in url:
                    path = fss_case_scraper.download_pdf(url, ntt_id, session)
                    if path:
                        pdf_path = path
                        raw_text = pdf_parser.extract_text(path)
                        if raw_text:
                            break
                    time.sleep(0.5)

            case = FssCaseReport(
                ntt_id=ntt_id,
                title=meta["title"],
                pub_date=meta.get("pub_date"),
                year=meta.get("year"),
                period=meta.get("period", ""),
                url=meta["url"],
                pdf_path=pdf_path,
                raw_text=raw_text[:50000] if raw_text else None,
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
