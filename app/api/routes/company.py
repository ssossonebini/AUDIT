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
    ReportCollected,
    NewsLine,
    NewsSummary,
    SectionLine,
    SectionsCollected,
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
    reprt_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """재무제표를 수집한다 — **전기말 사업보고서 + 당기중 최신 분·반기보고서**.

    사업보고서는 한 번에 3개년을 주고 주석도 완전하지만, 기말 시점에 멈춰
    있다. 기말감사 위험평가는 지금 상태를 봐야 하므로 최신 중간보고서를
    함께 받는다. 어느 쪽도 다른 쪽을 대신하지 못한다.

    bsns_year 를 직접 주면 그 한 건만 받는다 (reprt_code 기본값은 사업보고서).
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    if bsns_year:
        targets = [{
            "bsns_year": bsns_year,
            "reprt_code": reprt_code or dart_client.REPRT_ANNUAL,
            "report_label": dart_client.REPRT_LABELS.get(
                reprt_code or dart_client.REPRT_ANNUAL, "보고서"),
            "period_end": None,
        }]
    else:
        try:
            targets = _target_reports(db, company)
        except HTTPException as e:
            # 공시 목록을 못 받아도 사업보고서는 연도로 계산할 수 있다. 중간보고서만
            # 포기하고 나머지는 그대로 받는다 — 목록 조회 실패로 전부 잃지 않는다.
            logger.warning(f"정기보고서 목록을 받지 못했습니다: {e.detail}")
            targets = []

        if not targets:
            targets = [{
                "bsns_year": (company.audit_year or 0) - 1,
                "reprt_code": dart_client.REPRT_ANNUAL,
                "report_label": "사업보고서",
                "period_end": None,
            }]

    for target in targets:
        if target["bsns_year"] < 2015:
            raise HTTPException(
                status_code=400, detail="DART 재무제표는 2015년 이후만 제공됩니다."
            )

    reports: list[ReportCollected] = []
    for target in targets:
        year, code = target["bsns_year"], target["reprt_code"]

        divisions = _dart_call(
            dart_client.fetch_all_divisions, company.corp_code, year, code
        )
        if not divisions:
            logger.info(f"{year}년 {target['report_label']} 재무제표 없음")
            continue

        # 같은 (연도, 보고서)를 다시 수집하면 교체한다 (연결·별도 모두).
        # reprt_code 를 빼면 같은 해의 반기와 3분기가 서로를 지운다.
        db.query(FinancialStatement).filter(
            FinancialStatement.company_id == company.id,
            FinancialStatement.bsns_year == year,
            FinancialStatement.reprt_code == code,
        ).delete()

        annual = code == dart_client.REPRT_ANNUAL
        collected = []
        for fs_div, rows in divisions.items():
            counts: Counter = Counter()
            for row in rows:
                sj_div = row.get("sj_div", "")
                counts[sj_div] += 1
                db.add(FinancialStatement(
                    company_id=company.id,
                    bsns_year=year,
                    reprt_code=code,
                    fs_div=fs_div,
                    sj_div=sj_div,
                    sj_nm=row.get("sj_nm"),
                    account_id=row.get("account_id"),
                    account_nm=row.get("account_nm"),
                    account_detail=row.get("account_detail"),
                    ord=_as_int(row.get("ord")),
                    currency=row.get("currency"),
                    thstrm_nm=row.get("thstrm_nm"),
                    # 분기·반기 손익은 누적으로 맞춰 읽는다. 당기만 누적으로
                    # 읽고 전기를 3개월로 읽으면 전년 동기 대비가 어긋난다.
                    thstrm_amount=dart_client.current_amount(row),
                    frmtrm_amount=dart_client.prior_amount(row),
                    # 전전기는 사업보고서에만 있는 키다. 없으면 None 으로 둔다.
                    bfefrmtrm_amount=(
                        dart_client.parse_amount(row.get("bfefrmtrm_amount"))
                        if annual else None
                    ),
                ))

            collected.append(FinancialsCollected(
                fs_div=fs_div,
                label=dart_client.FS_DIV_LABELS[fs_div],
                total_rows=len(rows),
                by_statement=dict(counts),
            ))

        reports.append(ReportCollected(
            bsns_year=year, reprt_code=code,
            report_label=target["report_label"],
            period_end=target.get("period_end"),
            collected=collected,
        ))

    if not reports:
        raise HTTPException(
            status_code=404,
            detail="재무제표를 찾지 못했습니다. 공시 여부를 확인하세요.",
        )

    db.commit()

    lines = []
    for r in reports:
        parts = " · ".join(f"{c.label} {c.total_rows}행" for c in r.collected)
        span = "당기·전기·전전기" if r.reprt_code == dart_client.REPRT_ANNUAL \
            else "당기 누적·전년 동기"
        period = f" {r.period_end}" if r.period_end else ""
        missing = "" if len(r.collected) == 2 else " · 다른 구분은 공시되지 않았습니다"
        lines.append(
            f"{r.bsns_year}년 {r.report_label}{period} — {parts} ({span}{missing})"
        )

    annual_report = next(
        (r for r in reports if r.reprt_code == dart_client.REPRT_ANNUAL), reports[0]
    )
    return FinancialsSummary(
        bsns_year=annual_report.bsns_year,
        reports=reports,
        collected=annual_report.collected,
        message="재무제표 수집 — " + " / ".join(lines),
    )


@router.get("/companies/{company_id}/financials", response_model=list[FinancialLine])
def list_financials(
    company_id: int,
    bsns_year: Optional[int] = None,
    reprt_code: Optional[str] = None,
    fs_div: Optional[str] = None,
    sj_div: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(FinancialStatement).filter(FinancialStatement.company_id == company_id)
    if bsns_year:
        q = q.filter(FinancialStatement.bsns_year == bsns_year)
    if reprt_code:
        q = q.filter(FinancialStatement.reprt_code == reprt_code)
    if fs_div:
        q = q.filter(FinancialStatement.fs_div == fs_div)
    if sj_div:
        q = q.filter(FinancialStatement.sj_div == sj_div)
    return q.order_by(
        FinancialStatement.bsns_year.desc(), FinancialStatement.reprt_code,
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
    """보고서 원문을 받아 목차 단위로 쪼개 저장한다.

    재무제표 API 가 주지 않는 주석과 회사 기재 내용이 여기 있다 —
    특수관계자 거래, 우발부채, 핵심감사사항 등.

    **전기말 사업보고서와 당기중 최신 분·반기보고서를 함께 받는다.**
    중간보고서 주석은 K-IFRS 1034 에 따라 '직전 연차보고서 이후의 변동'만
    담은 요약본이라 사업보고서를 대체하지 못한다. 대신 기말 이후 무엇이
    달라졌는지는 여기서만 나온다. 첨부도 다르다 — 사업보고서에는 감사보고서가,
    중간보고서에는 검토보고서가 붙는다.

    본문만 8MB 가 넘으므로 통째로 두지 않고 목차로 나눈다. 분석 때는
    필요한 구간만 골라 읽는다.

    rcept_no 를 주면 그 보고서 하나만 받는다.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    if rcept_no:
        targets = [{
            "rcept_no": rcept_no, "bsns_year": None, "report_nm": None,
            "reprt_code": None, "report_label": "보고서",
        }]
    else:
        targets = _target_reports(db, company)

    if not targets:
        raise HTTPException(
            status_code=404,
            detail="정기보고서를 찾지 못했습니다. 공시된 사업보고서가 있는지 "
                   "확인하거나 rcept_no 를 직접 지정해주세요.",
        )

    reports: list[SectionsCollected] = []
    for target in targets:
        reports.append(_ingest_report_document(db, company, target))

    db.commit()

    lines = [
        f"{r.report_label} {r.total_sections}개 구간(감사 관련 {r.audit_relevant})"
        for r in reports
    ]
    documents: dict[str, int] = {}
    for r in reports:
        for label, count in r.documents.items():
            documents[label] = documents.get(label, 0) + count

    primary = next(
        (r for r in reports if r.report_label == "사업보고서"), reports[0]
    )
    return SectionsSummary(
        rcept_no=primary.rcept_no,
        bsns_year=primary.bsns_year,
        report_nm=primary.report_nm,
        reports=reports,
        documents=documents,
        total_sections=sum(r.total_sections for r in reports),
        audit_relevant=sum(r.audit_relevant for r in reports),
        total_chars=sum(r.total_chars for r in reports),
        message="원문 수집 — " + " / ".join(lines) +
                f" · 전체 {sum(r.total_chars for r in reports):,}자",
    )


def _ingest_report_document(
    db: Session, company: Company, target: dict
) -> SectionsCollected:
    """보고서 한 건의 원문을 받아 구간으로 저장한다."""
    rcept_no = target["rcept_no"]
    documents = _dart_call(dart_document.fetch_document, rcept_no)
    if not documents:
        raise HTTPException(status_code=404, detail="원문에 XML 이 없습니다.")

    db.query(ReportSection).filter(
        ReportSection.company_id == company.id,
        ReportSection.rcept_no == rcept_no,
    ).delete(synchronize_session=False)

    per_document: dict[str, int] = {}
    total_chars = relevant = 0

    labels = dart_document.document_labels(documents)

    # ZIP 엔트리 순서는 첨부가 먼저 오기도 한다. 본문을 앞에 둬야 화면에서
    # 처음 열리는 탭이 보고서 본문이 된다.
    ordered = sorted(documents.items(), key=lambda kv: ("_" in kv[0], kv[0]))

    for filename, xml_text in ordered:
        label = labels[filename]
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
                company_id=company.id, rcept_no=rcept_no, doc_label=label,
                bsns_year=target.get("bsns_year"),
                reprt_code=target.get("reprt_code"),
                report_nm=target.get("report_nm"),
                level=s["level"], title=s["title"],
                parent=s["parent"], section_no=s["section_no"],
                body=s["body"] or None, chars=s["chars"],
                audit_relevant=s["audit_relevant"],
            ))

    return SectionsCollected(
        rcept_no=rcept_no,
        bsns_year=target.get("bsns_year"),
        report_nm=target.get("report_nm"),
        report_label=target.get("report_label"),
        documents=per_document,
        total_sections=sum(per_document.values()),
        audit_relevant=relevant,
        total_chars=total_chars,
    )


@router.get("/companies/{company_id}/sections", response_model=list[SectionLine])
def list_sections(
    company_id: int,
    audit_only: bool = False,
    level: Optional[int] = None,
    reprt_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """목차만 돌려준다. 본문은 무거워 별도 조회로 뺀다."""
    q = db.query(ReportSection).filter(ReportSection.company_id == company_id)
    if audit_only:
        q = q.filter(ReportSection.audit_relevant.is_(True))
    if level:
        q = q.filter(ReportSection.level == level)
    if reprt_code:
        q = q.filter(ReportSection.reprt_code == reprt_code)
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


def _fiscal_month(company: Company) -> int:
    """결산월. 문자열로 저장돼 있고 비어 있을 수도 있다."""
    try:
        month = int(str(company.fiscal_month or "").strip())
    except ValueError:
        return 12
    return month if 1 <= month <= 12 else 12


def _periodic_reports(company: Company) -> list[dict]:
    """정기공시(A) 목록에서 정기보고서를 접수일 역순으로 읽는다.

    **이 목록이 곧 그 회사의 공시 주기다.** 분기보고서를 내는 회사인지
    반기만 내는 회사인지 따로 판정할 필요가 없다 — 낸 것만 여기 있다.

    [기재정정] 본은 같은 보고서의 최신본이므로 접수일이 늦은 쪽이 앞에 선다.
    """
    bgn_de, end_de = dart_client.fiscal_window(date.today())
    rows = _dart_call(
        dart_client.fetch_disclosure_list, company.corp_code, bgn_de, end_de, "A"
    )

    fiscal_month = _fiscal_month(company)
    reports = []
    for row in rows:
        report_nm = row.get("report_nm", "")
        info = dart_client.parse_periodic_report(report_nm, fiscal_month)
        if not info or not info["reprt_code"]:
            continue
        reports.append({
            **info,
            "rcept_no": row.get("rcept_no"),
            "rcept_dt": row.get("rcept_dt", ""),
            "report_nm": report_nm,
            "report_label": dart_client.REPRT_LABELS[info["reprt_code"]],
        })

    reports.sort(key=lambda r: r["rcept_dt"], reverse=True)
    return reports


def _target_reports(db: Session, company: Company) -> list[dict]:
    """분석 대상 보고서 — 전기말 사업보고서와 당기중 최신 분·반기보고서.

    사업보고서는 3개년 비교와 완전한 주석을 주고, 중간보고서는 지금 상태를
    준다. 어느 한쪽으로 대신할 수 없어 둘 다 받는다. 중간보고서 주석은
    K-IFRS 1034 에 따라 요약본이므로 사업보고서를 대체하지 않는다.

    중간보고서가 사업보고서보다 먼저 나온 것이라면 이미 사업보고서에 흡수된
    기간이므로 버린다 — 늘 '사업보고서 이후'만 의미가 있다.
    """
    reports = _periodic_reports(company)

    annual = next(
        (r for r in reports if r["reprt_code"] == dart_client.REPRT_ANNUAL), None
    )
    interim = next(
        (r for r in reports if r["reprt_code"] != dart_client.REPRT_ANNUAL), None
    )

    if annual and interim and interim["rcept_dt"] <= annual["rcept_dt"]:
        interim = None

    if annual is None:
        annual = _annual_from_disclosures(db, company)

    return [r for r in (annual, interim) if r]


def _annual_from_disclosures(db: Session, company: Company) -> Optional[dict]:
    """공시 목록을 못 받았을 때의 대비책 — 받아둔 주요정보에서 사업보고서를 찾는다.

    주요정보는 사업보고서에서 뽑은 것이라 payload 의 rcept_no 가 곧 사업보고서
    접수번호다. DART 호출이 들지 않는다.
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
            return {
                "kind": "사업",
                "reprt_code": dart_client.REPRT_ANNUAL,
                "report_label": "사업보고서",
                "bsns_year": row.bsns_year,
                "period_end": None,
                "rcept_no": rcept_no,
                "rcept_dt": "",
                "report_nm": None,
            }
    return None


def _latest_annual_report(
    db: Session, company: Company
) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """가장 최근 사업보고서의 (접수번호, 사업연도, 보고서명). 없으면 (None, None, None)."""
    annual = next(
        (r for r in _target_reports(db, company)
         if r["reprt_code"] == dart_client.REPRT_ANNUAL),
        None,
    )
    if not annual:
        return None, None, None
    return annual["rcept_no"], annual["bsns_year"], annual["report_nm"]


@router.post("/companies/{company_id}/sections/retag")
def retag_sections(company_id: int, db: Session = Depends(get_db)):
    """저장된 구간의 감사 관련 표시만 다시 매긴다.

    audit_relevant 는 저장 시점의 키워드 목록으로 굳는다. 목록이 바뀌어도
    이미 받아둔 구간에는 반영되지 않는데, 그걸 위해 원문 8MB 를 다시 내려받아
    파싱하는 것은 불리언 하나 값으로는 과하다. 제목만 다시 보면 된다.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")

    rows = (
        db.query(ReportSection)
        .filter(ReportSection.company_id == company.id)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="저장된 원문 구간이 없습니다. 보고서 원문 수집을 먼저 해주세요.",
        )

    added, removed = [], []
    for row in rows:
        now = dart_document.is_audit_relevant(row.title)
        if now == bool(row.audit_relevant):
            continue
        (added if now else removed).append(row.title)
        row.audit_relevant = now

    db.commit()
    total = sum(1 for r in rows if r.audit_relevant)

    changed = f" — 추가 {len(added)}개" if added else ""
    changed += f" · 해제 {len(removed)}개" if removed else ""
    return {
        "total_sections": len(rows),
        "audit_relevant": total,
        "added": added,
        "removed": removed,
        "message": f"감사 관련 표시 {total}개{changed or ' (변동 없음)'}",
    }
