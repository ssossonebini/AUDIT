"""
금융감독원 중점심사 회계이슈 API
"""
import logging
import time
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import FssArticle, AuditIssue
from app.schemas.fss import FssArticleSchema, FssArticleListItem, CrawlStatus
from app.crawler import fss_scraper
from app.crawler import pdf_parser

logger = logging.getLogger(__name__)
router = APIRouter()

# 크롤링 상태 (간이 상태 저장)
_crawl_state: dict = {"running": False, "total": 0, "processed": 0, "message": ""}


@router.get("/years", response_model=list[int])
def get_available_years(db: Session = Depends(get_db)):
    """데이터가 있는 연도 목록 반환"""
    rows = db.query(FssArticle.year).distinct().order_by(FssArticle.year.desc()).all()
    return [r.year for r in rows if r.year]


@router.get("/articles", response_model=list[FssArticleListItem])
def list_articles(year: Optional[int] = None, db: Session = Depends(get_db)):
    """보도자료 목록 조회 (연도 필터 가능)"""
    q = db.query(FssArticle)
    if year:
        q = q.filter(FssArticle.year == year)
    articles = q.order_by(FssArticle.pub_date.desc()).all()

    result = []
    for a in articles:
        result.append(
            FssArticleListItem(
                id=a.id,
                ntt_id=a.ntt_id,
                title=a.title,
                pub_date=a.pub_date,
                year=a.year,
                url=a.url,
                summary=a.summary,
                issue_count=len(a.issues),
            )
        )
    return result


@router.get("/articles/{article_id}", response_model=FssArticleSchema)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """보도자료 상세 조회"""
    article = db.query(FssArticle).filter(FssArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return article


@router.post("/articles/{article_id}/summarize")
def summarize_article(article_id: int, db: Session = Depends(get_db)):
    """PDF 내용을 Claude AI로 요약 (raw_text 없으면 실시간 다운로드)"""
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일에 키를 추가해주세요.")

    article = db.query(FssArticle).filter(FssArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    # raw_text가 없으면 PDF 실시간 다운로드
    if not article.raw_text:
        try:
            session = fss_scraper._session()
            detail = fss_scraper.fetch_article_detail(article.ntt_id, session)
            raw_text = ""
            for attachment in detail.get("attachments", []):
                url = attachment["url"]
                if ".pdf" in url.lower() or "fileDown" in url:
                    path = fss_scraper.download_pdf(url, article.ntt_id, session)
                    if path:
                        raw_text = pdf_parser.extract_text(path)
                        break
            if not raw_text:
                raise HTTPException(status_code=404, detail="PDF 파일을 찾을 수 없습니다. 원문 보기에서 직접 확인해주세요.")
            # DB에 저장
            article.raw_text = raw_text[:50000]
            db.commit()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF 다운로드 중 오류: {str(e)}")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    text = article.raw_text[:30000]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""다음은 금융감독원의 중점심사 회계이슈 보도자료 PDF 내용입니다.
아래 항목으로 핵심 내용을 한국어로 요약해주세요:

1. 전체 개요 (2-3문장)
2. 주요 회계이슈 목록 (각 이슈명과 한 줄 설명)
3. 기업 및 감사인에 대한 주요 시사점

PDF 내용:
{text}"""
            }
        ]
    )

    raw = message.content[0].text.strip()
    structured = _parse_markdown_summary(raw)
    return {"summary": raw, "structured": structured}


def _parse_markdown_summary(text: str) -> dict:
    """AI가 반환한 마크다운 텍스트를 구조화된 dict로 변환"""
    lines = text.splitlines()

    overview = ""
    issues = []
    companies = []
    auditors = []

    section = None  # "overview" | "issues" | "companies" | "auditors"
    overview_lines = []

    for line in lines:
        stripped = line.strip()

        # 섹션 헤더 감지
        if re.search(r"전체\s*개요", stripped):
            section = "overview"
            continue
        if re.search(r"회계이슈\s*목록|주요\s*회계이슈", stripped):
            section = "issues"
            continue
        if re.search(r"기업\s*(대상|에\s*대한)", stripped):
            section = "companies"
            continue
        if re.search(r"감사인\s*(대상|에\s*대한)", stripped):
            section = "auditors"
            continue
        if re.search(r"시사점", stripped) and section not in ("companies", "auditors"):
            section = "companies"
            continue

        # 구분선·빈 줄·소제목 skip
        if not stripped or re.match(r"^-{3,}$", stripped):
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue

        if section == "overview":
            clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
            overview_lines.append(clean)

        elif section == "issues":
            # 표 행: | 이슈명 | 설명 |
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]
                if len(cells) >= 2 and not re.match(r"^[-:]+$", cells[0]):
                    title = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[0])
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[-1])
                    if not re.match(r"^(이슈|순번|번호|No)", title):
                        issues.append({
                            "number": len(issues) + 1,
                            "title": title,
                            "description": desc,
                        })
            # 번호 목록: ① 이슈명: 설명 or - **이슈**: 설명
            else:
                m = re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩\-\*\d\.]+\s*\*?\*?([^*:：]+)\*?\*?[：:]\s*(.+)", stripped)
                if m:
                    title = m.group(1).strip()
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", m.group(2).strip())
                    issues.append({"number": len(issues) + 1, "title": title, "description": desc})

        elif section == "companies":
            if stripped.startswith("-") or stripped.startswith("•"):
                item = re.sub(r"^[-•]\s*", "", stripped)
                item = re.sub(r"\*\*([^*]+)\*\*", r"\1", item)
                companies.append(item)

        elif section == "auditors":
            if stripped.startswith("-") or stripped.startswith("•"):
                item = re.sub(r"^[-•]\s*", "", stripped)
                item = re.sub(r"\*\*([^*]+)\*\*", r"\1", item)
                auditors.append(item)

    overview = " ".join(overview_lines[:4])

    return {
        "overview": overview,
        "issues": issues,
        "implications": {
            "companies": companies,
            "auditors": auditors,
        },
    }


@router.post("/crawl", response_model=CrawlStatus)
def start_crawl(background_tasks: BackgroundTasks, max_pages: int = 5, db: Session = Depends(get_db)):
    """크롤링 시작 (백그라운드 작업)"""
    if _crawl_state["running"]:
        return CrawlStatus(
            status="running",
            message="이미 크롤링이 진행 중입니다.",
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )

    background_tasks.add_task(_do_crawl, max_pages, db)
    return CrawlStatus(status="started", message="크롤링을 시작했습니다.")


@router.get("/crawl/status", response_model=CrawlStatus)
def crawl_status():
    """크롤링 진행 상태 조회"""
    if _crawl_state["running"]:
        return CrawlStatus(
            status="running",
            message=_crawl_state["message"],
            total=_crawl_state["total"],
            processed=_crawl_state["processed"],
        )
    return CrawlStatus(
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
        session = fss_scraper._session()

        # 1단계: 목록 수집
        articles_meta = fss_scraper.fetch_article_list(max_pages=max_pages)
        _crawl_state["total"] = len(articles_meta)
        _crawl_state["message"] = f"총 {len(articles_meta)}개 게시글 발견"

        for meta in articles_meta:
            ntt_id = meta["ntt_id"]
            _crawl_state["message"] = f"처리 중: {meta['title'][:30]}..."

            # 이미 DB에 있는 경우 건너뜀
            existing = db.query(FssArticle).filter(FssArticle.ntt_id == ntt_id).first()
            if existing and existing.summary:
                _crawl_state["processed"] += 1
                continue

            # 2단계: 상세 페이지에서 첨부파일 URL 추출
            detail = fss_scraper.fetch_article_detail(ntt_id, session)
            time.sleep(0.5)

            pdf_path = None
            raw_text = ""

            # 3단계: PDF 다운로드 및 파싱
            for attachment in detail.get("attachments", []):
                url = attachment["url"]
                if ".pdf" in url.lower() or "fileDown" in url:
                    path = fss_scraper.download_pdf(url, ntt_id, session)
                    if path:
                        pdf_path = path
                        raw_text = pdf_parser.extract_text(path)
                        break
                    time.sleep(0.5)

            # 4단계: 이슈 파싱 및 요약
            issues_data = pdf_parser.parse_audit_issues(raw_text) if raw_text else []
            summary = pdf_parser.build_summary(raw_text, issues_data) if raw_text else ""

            # 5단계: DB 저장
            if existing:
                article = existing
            else:
                article = FssArticle(
                    ntt_id=ntt_id,
                    title=meta["title"],
                    pub_date=meta.get("pub_date"),
                    year=meta.get("year"),
                    url=meta["url"],
                )
                db.add(article)
                db.flush()

            article.pdf_path = pdf_path
            article.raw_text = raw_text[:50000] if raw_text else None
            article.summary = summary

            # 기존 이슈 삭제 후 재등록
            db.query(AuditIssue).filter(AuditIssue.article_id == article.id).delete()
            for issue in issues_data:
                db.add(AuditIssue(
                    article_id=article.id,
                    issue_number=issue["issue_number"],
                    issue_title=issue["issue_title"],
                    description=issue.get("description"),
                ))

            db.commit()
            _crawl_state["processed"] += 1

        _crawl_state["message"] = f"크롤링 완료: {_crawl_state['processed']}개 처리"

    except Exception as e:
        logger.exception("크롤링 중 오류 발생")
        _crawl_state["message"] = f"오류: {str(e)}"
    finally:
        _crawl_state["running"] = False
