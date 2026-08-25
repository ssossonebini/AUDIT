"""
회사 프로젝트 관리 + DART 재무제표 수집 API
"""
import json
import logging
from collections import Counter
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import workspace
from app.db.database import get_db
from app.db.models import (
    Company, DisclosureFiling, DisclosureItem, FinancialStatement,
)
from app.schemas.company import (
    CompanyCreate,
    CompanyListItem,
    CompanySchema,
    CorpSearchResult,
    DisclosureCollected,
    DisclosureLine,
    DisclosuresSummary,
    FilingLine,
    FilingsSummary,
    FinancialLine,
    FinancialsCollected,
    FinancialsSummary,
)
from app.crawler import dart_client

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
