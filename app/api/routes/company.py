"""
회사 프로젝트 관리 + DART 재무제표 수집 API
"""
import json
import logging
import re
from collections import Counter
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import exporter, workspace
from app.db.database import get_db
from app.db.models import (
    Company, CompanyNews, DisclosureFiling, DisclosureItem, FinancialStatement,
    ReportSection,
)
from app.schemas.company import (
    CompanyCreate,
    CompanyListItem,
    CompanySchema,
    CorpSearchResult,
    ExportSummary,
    DisclosureCollected,
    DisclosureLine,
    DisclosuresSummary,
    FilingLine,
    FilingsSummary,
    FinancialLine,
    FinancialsCollected,
    FinancialsSummary,
    NewsLine,
    NewsSummary,
    SectionLine,
    SectionsSummary,
)
from app.core.config import settings
from app.crawler import dart_client, dart_document, news_scraper

logger = logging.getLogger(__name__)
router = APIRouter()


def _dart_call(fn, *args, **kwargs):
    """DartError 를 사용자에게 보여줄 HTTP 오류로 바꾼다."""
    try:
        return fn(*args, **kwargs)
    except dart_client.DartError as e:
        status = 404 if e.status == "013" else 502
        if e.status in ("010", "011", "012"):
            status = 503
        raise HTTPException(status_code=status, detail=f"DART: {e.message}")
    except Exception as e:
        logger.exception("DART 호출 실패")
        raise HTTPException(status_code=502, detail=f"DART 호출 실패: {e}")


@router.get("/search", response_model=list[CorpSearchResult])
def search_corp(name: str, listed_only: bool = True, db: Session = Depends(get_db)):
    """회사명으로 DART 고유번호를 찾는다 (등록 전 확인용).

    첫 호출은 전체 고유번호 파일(약 100MB 압축 해제)을 내려받아 캐시하므로
    수십 초가 걸릴 수 있다. 이후에는 메모리 캐시를 쓴다.
    """
    if not name.strip():
        raise HTTPException(status_code=400, detail="회사명을 입력하세요.")
    return _dart_call(dart_client.search_corp, name, listed_only=listed_only)


@router.get("/companies", response_model=list[CompanyListItem])
def list_companies(audit_year: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Company)
    if audit_year:
        q = q.filter(Company.audit_year == audit_year)
    return q.order_by(Company.created_at.desc()).all()


@router.get("/companies/{company_id}", response_model=CompanySchema)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")
    return company


@router.post("/companies", response_model=CompanySchema)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """회사를 등록하고 작업폴더를 만든다. 기업개황은 DART에서 채운다."""
    existing = db.query(Company).filter(Company.corp_code == payload.corp_code).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"이미 등록된 회사입니다: {existing.corp_name} ({existing.audit_year}년)",
        )

    info = _dart_call(dart_client.fetch_company, payload.corp_code)
    corp_name = info.get("corp_name") or payload.corp_code

    path = workspace.create(payload.audit_year, corp_name)

    company = Company(
        corp_code=payload.corp_code,
        corp_name=corp_name,
        stock_code=(info.get("stock_code") or "").strip() or None,
        industry_code=info.get("induty_code"),
        ceo_name=info.get("ceo_nm"),
        fiscal_month=info.get("acc_mt"),
        audit_year=payload.audit_year,
        workspace_path=str(path),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/companies/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    """DB 레코드만 지운다. workspace 폴더는 자료가 들어 있으므로 남긴다."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    name, path = company.corp_name, company.workspace_path
    db.delete(company)
    db.commit()
    return {
        "message": f"{name} 등록을 해제했습니다.",
        "note": f"작업폴더는 남아 있습니다: {path}",
    }


@router.post("/companies/{company_id}/financials", response_model=FinancialsSummary)
def collect_financials(
    company_id: int,
    bsns_year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """사업보고서 재무제표를 수집한다 — 한 번에 3개년이 들어온다.

    bsns_year 를 주지 않으면 감사대상연도의 직전 연도를 쓴다. 감사대상연도의
    사업보고서는 아직 공시되지 않았기 때문이다.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    year = bsns_year or ((company.audit_year or 0) - 1)
    if year < 2015:
        raise HTTPException(
            status_code=400, detail="DART 재무제표는 2015년 이후만 제공됩니다."
        )

    divisions = _dart_call(dart_client.fetch_all_divisions, company.corp_code, year)
    if not divisions:
        raise HTTPException(
            status_code=404,
            detail=f"{year}년 사업보고서 재무제표가 없습니다. 공시 여부를 확인하세요.",
        )

    # 같은 연도를 다시 수집하면 교체한다 (연결·별도 모두)
    db.query(FinancialStatement).filter(
        FinancialStatement.company_id == company.id,
        FinancialStatement.bsns_year == year,
    ).delete()

    collected = []
    for fs_div, rows in divisions.items():
        counts: Counter = Counter()
        for row in rows:
            sj_div = row.get("sj_div", "")
            counts[sj_div] += 1
            db.add(FinancialStatement(
                company_id=company.id,
                bsns_year=year,
                reprt_code=dart_client.REPRT_ANNUAL,
                fs_div=fs_div,
                sj_div=sj_div,
                sj_nm=row.get("sj_nm"),
                account_id=row.get("account_id"),
                account_nm=row.get("account_nm"),
                account_detail=row.get("account_detail"),
                ord=_as_int(row.get("ord")),
                currency=row.get("currency"),
                thstrm_nm=row.get("thstrm_nm"),
                thstrm_amount=dart_client.current_amount(row),
                frmtrm_amount=dart_client.prior_amount(row),
                # 사업보고서에만 있는 키다. 없으면 None 으로 둔다.
                bfefrmtrm_amount=dart_client.parse_amount(row.get("bfefrmtrm_amount")),
            ))

        collected.append(FinancialsCollected(
            fs_div=fs_div,
            label=dart_client.FS_DIV_LABELS[fs_div],
            total_rows=len(rows),
            by_statement=dict(counts),
        ))

    db.commit()

    parts = [f"{c.label} {c.total_rows}행" for c in collected]
    missing = "" if len(collected) == 2 else " (다른 구분은 공시되지 않았습니다)"
    return FinancialsSummary(
        bsns_year=year,
        collected=collected,
        message=f"{year}년 재무제표 수집 — {' · '.join(parts)}"
                f" · 당기·전기·전전기 포함{missing}",
    )


@router.get("/companies/{company_id}/financials", response_model=list[FinancialLine])
def list_financials(
    company_id: int,
    bsns_year: Optional[int] = None,
    fs_div: Optional[str] = None,
    sj_div: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(FinancialStatement).filter(FinancialStatement.company_id == company_id)
    if bsns_year:
        q = q.filter(FinancialStatement.bsns_year == bsns_year)
    if fs_div:
        q = q.filter(FinancialStatement.fs_div == fs_div)
    if sj_div:
        q = q.filter(FinancialStatement.sj_div == sj_div)
    return q.order_by(
        FinancialStatement.fs_div, FinancialStatement.sj_div, FinancialStatement.ord
    ).all()


def _as_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@router.post("/companies/{company_id}/disclosures", response_model=DisclosuresSummary)
def collect_disclosures(
    company_id: int,
    bsns_year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """정기보고서 주요정보를 수집한다 (배당·증자·자기주식·출자·최대주주·감사의견).

    수집 범위는 **직전 회계연도 개시일 ~ 오늘** 사이에 공시된 사업보고서다.
    사업보고서는 사업연도 종료 후 90일 안에 제출되므로, 그 창에는 사업연도
    두 해분이 들어온다 (2026-08-26 기준이면 2024·2025). 주요정보 API 자체는
    날짜가 아니라 사업연도로 조회되므로 이렇게 환산해서 부른다.

    bsns_year 를 주면 그 해만 수집한다.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    today = date.today()
    years = [bsns_year] if bsns_year else dart_client.target_business_years(today)
    years = [y for y in years if y >= 2015]
    if not years:
        raise HTTPException(
            status_code=400, detail="DART 주요정보는 2015년 이후만 제공됩니다."
        )

    # 같은 사업연도를 다시 수집하면 교체한다
    db.query(DisclosureItem).filter(
        DisclosureItem.company_id == company.id,
        DisclosureItem.bsns_year.in_(years),
    ).delete(synchronize_session=False)

    collected: list[DisclosureCollected] = []
    total = 0

    for category, (api_file, label) in dart_client.MAJOR_INFO_APIS.items():
        rows_saved, years_with_rows, error = 0, [], None

        for year in years:
            try:
                rows = dart_client.fetch_major_info(company.corp_code, year, api_file)
            except dart_client.DartError as e:
                if e.status == "013":      # 해당 연도에 그 항목이 없을 뿐이다
                    continue
                # 항목 하나가 실패해도 나머지는 계속 모은다
                error = e.message
                logger.warning(f"{label} {year} 실패: {e}")
                break
            except Exception as e:
                error = str(e)
                logger.exception(f"{label} {year} 실패")
                break

            for row in rows:
                db.add(DisclosureItem(
                    company_id=company.id,
                    category=category,
                    api_file=api_file,
                    bsns_year=year,
                    reprt_code=dart_client.REPRT_ANNUAL,
                    rcept_no=row.get("rcept_no"),
                    payload=json.dumps(row, ensure_ascii=False),
                ))
            if rows:
                rows_saved += len(rows)
                years_with_rows.append(year)

        total += rows_saved
        collected.append(DisclosureCollected(
            category=category, label=label,
            rows=rows_saved, years=years_with_rows, error=error,
        ))

    db.commit()

    start = date(today.year - 1, 1, 1)
    period = f"{start.isoformat()} ~ {today.isoformat()} 공시분 (사업연도 {years[0]}~{years[-1]})"
    failed = [c.label for c in collected if c.error]
    note = f" · 실패 {len(failed)}종({', '.join(failed)})" if failed else ""

    return DisclosuresSummary(
        years=years,
        period=period,
        collected=collected,
        total_rows=total,
        message=f"주요정보 {total}행 수집 — {period}{note}",
    )


@router.get("/companies/{company_id}/disclosures", response_model=list[DisclosureLine])
def list_disclosures(
    company_id: int,
    category: Optional[str] = None,
    bsns_year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(DisclosureItem).filter(DisclosureItem.company_id == company_id)
    if category:
        q = q.filter(DisclosureItem.category == category)
    if bsns_year:
        q = q.filter(DisclosureItem.bsns_year == bsns_year)

    rows = q.order_by(DisclosureItem.category, DisclosureItem.bsns_year.desc()).all()
    return [
        DisclosureLine(
            id=r.id, category=r.category, bsns_year=r.bsns_year,
            rcept_no=r.rcept_no, payload=_safe_json(r.payload),
        )
        for r in rows
    ]


def _safe_json(text: Optional[str]) -> dict:
    try:
        return json.loads(text) if text else {}
    except (TypeError, ValueError):
        return {}


@router.post("/companies/{company_id}/filings", response_model=FilingsSummary)
def collect_filings(
    company_id: int,
    pblntf_ty: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """공시 목록을 수집한다 — 기중에 제출된 이벤트 공시.

    수집 창은 **직전 회계연도 개시일 ~ 오늘**이다. 2026년 기말감사라면
    2025-01-01 ~ 오늘이 되어, 2025년 1역년 공시와 2026년 기중 공시가
    모두 들어온다. 주요정보(DS002)가 사업보고서 시점의 '현황'이라면
    이쪽은 자기주식취득결정·합병결정·대규모내부거래처럼 기간 중에
    실제로 벌어진 '이벤트'다.

    pblntf_ty 를 주면 그 유형만, 없으면 감사 관련성이 높은 네 유형
    (주요사항보고·외부감사관련·거래소공시·공정위공시)을 모은다.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    today = date.today()
    bgn_de, end_de = dart_client.fiscal_window(today)
    types = (pblntf_ty,) if pblntf_ty else dart_client.DEFAULT_PUBLIC_TYPES

    rows: list[dict] = []
    for ty in types:
        rows.extend(
            _dart_call(
                dart_client.fetch_disclosure_list,
                company.corp_code, bgn_de, end_de, ty,
            )
        )

    # 같은 공시가 여러 유형으로 잡히기도 한다 (접수번호로 중복 제거)
    unique: dict[str, dict] = {}
    for row in rows:
        rcept_no = row.get("rcept_no")
        if rcept_no and rcept_no not in unique:
            unique[rcept_no] = row

    db.query(DisclosureFiling).filter(
        DisclosureFiling.company_id == company.id
    ).delete(synchronize_session=False)

    by_type: Counter = Counter()
    by_tag: Counter = Counter()
    untagged = 0

    for row in unique.values():
        tag = dart_client.tag_filing(row.get("report_nm", ""))
        ty = row.get("pblntf_ty") or ""
        by_type[dart_client.PUBLIC_TYPES.get(ty, ty or "기타")] += 1
        if tag:
            by_tag[tag] += 1
        else:
            untagged += 1

        db.add(DisclosureFiling(
            company_id=company.id,
            rcept_no=row.get("rcept_no"),
            report_nm=row.get("report_nm"),
            flr_nm=row.get("flr_nm"),
            rcept_dt=row.get("rcept_dt"),
            pblntf_ty=ty,
            tag=tag,
            rm=row.get("rm"),
        ))

    db.commit()

    period = f"{bgn_de[:4]}-{bgn_de[4:6]}-{bgn_de[6:]} ~ {end_de[:4]}-{end_de[4:6]}-{end_de[6:]}"
    return FilingsSummary(
        period=period,
        total_rows=len(unique),
        by_type=dict(by_type),
        by_tag=dict(by_tag),
        untagged=untagged,
        message=f"공시 {len(unique)}건 수집 — {period}"
                + (f" · 감사 관련 태그 {sum(by_tag.values())}건" if by_tag else ""),
    )


@router.get("/companies/{company_id}/filings", response_model=list[FilingLine])
def list_filings(
    company_id: int,
    tag: Optional[str] = None,
    pblntf_ty: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(DisclosureFiling).filter(DisclosureFiling.company_id == company_id)
    if tag:
        q = q.filter(DisclosureFiling.tag == tag)
    if pblntf_ty:
        q = q.filter(DisclosureFiling.pblntf_ty == pblntf_ty)

    rows = q.order_by(DisclosureFiling.rcept_dt.desc()).all()
    return [
        FilingLine(
            id=r.id, rcept_no=r.rcept_no, report_nm=r.report_nm, flr_nm=r.flr_nm,
            rcept_dt=r.rcept_dt, pblntf_ty=r.pblntf_ty, tag=r.tag, rm=r.rm,
            dart_url=r.dart_url,
        )
        for r in rows
    ]


@router.post("/companies/{company_id}/news", response_model=NewsSummary)
def collect_news(company_id: int, db: Session = Depends(get_db)):
    """회사 뉴스를 수집하고 감사 어서션 4분류로 태깅한다.

    수집 창은 공시와 같다 — 직전 회계연도 개시일 ~ 오늘.
    ANTHROPIC_API_KEY 가 없으면 태깅 없이 목록만 저장한다.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    today = date.today()
    bgn_raw, end_raw = dart_client.fiscal_window(today)
    bgn = f"{bgn_raw[:4]}-{bgn_raw[4:6]}-{bgn_raw[6:]}"
    end = f"{end_raw[:4]}-{end_raw[4:6]}-{end_raw[6:]}"

    try:
        items = news_scraper.collect(company.corp_name, bgn, end)
    except Exception as e:
        logger.exception("뉴스 수집 실패")
        raise HTTPException(status_code=502, detail=f"뉴스 수집 실패: {e}")

    if not items:
        raise HTTPException(
            status_code=404,
            detail="수집된 뉴스가 없습니다. 회사명이 정확한지 확인해주세요.",
        )

    db.query(CompanyNews).filter(
        CompanyNews.company_id == company.id
    ).delete(synchronize_session=False)

    api_key = settings.ANTHROPIC_API_KEY
    by_tag: Counter = Counter()
    untagged = 0

    for item in items:
        tag, reason = None, ""
        if api_key:
            result = news_scraper.classify(item["title"], company.corp_name, api_key)
            tag, reason = result["tag"], result["reason"]

        if tag:
            by_tag[tag] += 1
        else:
            untagged += 1

        db.add(CompanyNews(
            company_id=company.id,
            title=item["title"],
            url=item.get("url"),
            source=item.get("source"),
            published_at=item.get("published_at"),
            tag=tag,
            ai_reason=reason or None,
            query=item.get("query"),
        ))

    db.commit()

    period = f"{bgn} ~ {end}"
    note = "" if api_key else " · ANTHROPIC_API_KEY 가 없어 태깅을 건너뜀"
    return NewsSummary(
        period=period,
        fetched=len(items),
        saved=len(items),
        by_tag=dict(by_tag),
        untagged=untagged,
        ai_used=bool(api_key),
        message=f"뉴스 {len(items)}건 수집 — {period}"
                + (f" · 감사 관련 {sum(by_tag.values())}건" if by_tag else "")
                + note,
    )


@router.get("/companies/{company_id}/news", response_model=list[NewsLine])
def list_news(
    company_id: int,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(CompanyNews).filter(CompanyNews.company_id == company_id)
    if tag:
        q = q.filter(CompanyNews.tag == tag)
    return q.order_by(CompanyNews.published_at.desc()).all()


@router.post("/companies/{company_id}/export", response_model=ExportSummary)
def export_analysis(company_id: int, db: Session = Depends(get_db)):
    """작업폴더에 00_INPUT.md 와 상세 파일을 쓴다.

    raw_text 는 담지 않는다 — 전부 펼치면 컨텍스트에 들어가지 않는다.
    다이제스트만 쓰고, 원문이 필요하면 audit.db 를 조회하도록 안내한다.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    try:
        result = exporter.export(db, company)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"파일 쓰기 실패: {e}")

    total_chars = sum(result["chars"].values())
    entry = result["chars"].get("00_INPUT.md", 0)

    return ExportSummary(
        root=result["root"],
        files=result["files"],
        chars=result["chars"],
        approx_tokens=round(entry / 1.7),
        message=f"{len(result['files'])}개 파일 생성 — {result['root']} "
                f"(00_INPUT.md 약 {round(entry / 1.7):,} 토큰, 전체 {total_chars:,}자)",
    )


@router.post("/companies/{company_id}/sections", response_model=SectionsSummary)
def collect_sections(
    company_id: int,
    rcept_no: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """사업보고서 원문을 받아 목차 단위로 쪼개 저장한다.

    재무제표 API 가 주지 않는 주석과 회사 기재 내용이 여기 있다 —
    특수관계자 거래, 우발부채, 핵심감사사항 등.

    본문만 8MB 가 넘으므로 통째로 두지 않고 목차로 나눈다. 분석 때는
    필요한 구간만 골라 읽는다.

    rcept_no 를 주지 않으면 수집해 둔 주요정보에서 가장 최근 사업보고서를 찾는다.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    target, year, report_nm = rcept_no, None, None
    if not target:
        target, year, report_nm = _latest_annual_report(db, company)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="사업보고서를 찾지 못했습니다. 공시된 사업보고서가 있는지 "
                   "확인하거나 rcept_no 를 직접 지정해주세요.",
        )

    documents = _dart_call(dart_document.fetch_document, target)
    if not documents:
        raise HTTPException(status_code=404, detail="원문에 XML 이 없습니다.")

    db.query(ReportSection).filter(
        ReportSection.company_id == company.id,
        ReportSection.rcept_no == target,
    ).delete(synchronize_session=False)

    per_document: dict[str, int] = {}
    total_chars = relevant = 0

    for filename, xml_text in documents.items():
        label = dart_document.document_label(filename)
        try:
            sections = dart_document.parse_sections(xml_text)
        except Exception as e:
            logger.exception(f"원문 파싱 실패 ({filename})")
            raise HTTPException(status_code=502, detail=f"원문 파싱 실패: {e}")

        per_document[label] = len(sections)
        for s in sections:
            total_chars += s["chars"]
            relevant += 1 if s["audit_relevant"] else 0
            db.add(ReportSection(
                company_id=company.id, rcept_no=target, doc_label=label,
                bsns_year=year, level=s["level"], title=s["title"],
                parent=s["parent"], section_no=s["section_no"],
                body=s["body"] or None, chars=s["chars"],
                audit_relevant=s["audit_relevant"],
            ))

    db.commit()
    total = sum(per_document.values())

    label = report_nm or (f"{year}년 사업보고서" if year else "사업보고서")
    return SectionsSummary(
        rcept_no=target, bsns_year=year, report_nm=report_nm,
        documents=per_document, total_sections=total,
        audit_relevant=relevant, total_chars=total_chars,
        message=f"{label} 원문 {total}개 구간 저장 — 감사 관련 {relevant}개 "
                f"· 전체 {total_chars:,}자 (접수번호 {target})",
    )


@router.get("/companies/{company_id}/sections", response_model=list[SectionLine])
def list_sections(
    company_id: int,
    audit_only: bool = False,
    level: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """목차만 돌려준다. 본문은 무거워 별도 조회로 뺀다."""
    q = db.query(ReportSection).filter(ReportSection.company_id == company_id)
    if audit_only:
        q = q.filter(ReportSection.audit_relevant.is_(True))
    if level:
        q = q.filter(ReportSection.level == level)
    return q.order_by(ReportSection.id).all()


@router.get("/companies/{company_id}/sections/{section_id}")
def get_section(company_id: int, section_id: int, db: Session = Depends(get_db)):
    """구간 하나의 본문."""
    section = (
        db.query(ReportSection)
        .filter(ReportSection.id == section_id,
                ReportSection.company_id == company_id)
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="구간을 찾을 수 없습니다.")
    return {
        "id": section.id, "title": section.title, "parent": section.parent,
        "doc_label": section.doc_label, "chars": section.chars,
        "body": section.body or "",
    }


ANNUAL_REPORT_NAME = re.compile(r"사업보고서\s*\((\d{4})[.\s]")


def _latest_annual_report(
    db: Session, company: Company
) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """가장 최근 사업보고서의 (접수번호, 사업연도, 보고서명) 을 찾는다.

    이미 받아둔 주요정보에서 먼저 본다 — 주요정보는 사업보고서에서 뽑은 것이라
    payload 의 rcept_no 가 곧 사업보고서 접수번호이고, 호출이 들지 않는다.

    없으면 DART 공시 목록(정기공시 A)에서 직접 찾는다. 그래야 주요정보를
    수집하지 않은 상태에서도 원문을 받을 수 있다 — 수집 순서에 매이지 않는다.
    """
    rows = (
        db.query(DisclosureItem)
        .filter(DisclosureItem.company_id == company.id)
        .order_by(DisclosureItem.bsns_year.desc())
        .all()
    )
    for row in rows:
        rcept_no = _safe_json(row.payload).get("rcept_no") or row.rcept_no
        if rcept_no:
            return rcept_no, row.bsns_year, None

    return _find_annual_report_at_dart(company)


def _find_annual_report_at_dart(
    company: Company,
) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """정기공시(A) 목록에서 가장 최근 사업보고서를 고른다.

    반기·분기보고서가 섞여 오므로 보고서명으로 걸러낸다. [기재정정] 본은
    같은 사업연도의 최신본이므로 접수일이 늦은 쪽을 택하면 자연히 잡힌다.
    """
    bgn_de, end_de = dart_client.fiscal_window(date.today())
    rows = _dart_call(
        dart_client.fetch_disclosure_list, company.corp_code, bgn_de, end_de, "A"
    )

    candidates = []
    for row in rows:
        match = ANNUAL_REPORT_NAME.search(row.get("report_nm", ""))
        if match:
            candidates.append((row.get("rcept_dt", ""), row, int(match.group(1))))

    if not candidates:
        return None, None, None

    _, row, year = max(candidates, key=lambda c: c[0])
    return row.get("rcept_no"), year, row.get("report_nm")
