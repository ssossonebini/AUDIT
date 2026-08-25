"""
회사 프로젝트 관리 + DART 재무제표 수집 API
"""
import logging
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import workspace
from app.db.database import get_db
from app.db.models import Company, FinancialStatement
from app.schemas.company import (
    CompanyCreate,
    CompanyListItem,
    CompanySchema,
    CorpSearchResult,
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
