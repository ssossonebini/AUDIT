"""회사 작업폴더로 분석자료를 내보낸다.

설계 원칙 하나가 전부다 — **raw_text 를 덤프하지 않는다.**

수집한 PDF 전문을 전부 펼치면 45만 토큰이 넘어 컨텍스트에 들어가지 않는다.
그래서 00_INPUT.md 는 다이제스트만 담고, 원문이 필요해지는 순간에만
audit.db 를 직접 조회하도록 안내한다. 분량이 큰 부분(재무제표 전 계정,
미분류 포함 전체 뉴스)은 하위 폴더에 따로 떨어뜨려 Read 한 번 거리에 둔다.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import (
    AuditIssue,
    Company,
    CompanyNews,
    DisclosureFiling,
    DisclosureItem,
    FinancialStatement,
    FssArticle,
    FssCaseReport,
)

logger = logging.getLogger(__name__)

# 00_INPUT.md 에 올릴 계정. 나머지는 01_financials 상세 파일에서 본다.
KEY_ACCOUNTS = (
    "자산총계", "유동자산", "비유동자산",
    "부채총계", "유동부채", "비유동부채",
    "자본총계", "이익잉여금",
    "매출액", "수익(매출액)", "영업이익", "영업이익(손실)",
    "법인세비용차감전순이익", "당기순이익", "당기순이익(손실)",
    "영업활동현금흐름", "영업활동으로인한현금흐름",
    "투자활동현금흐름", "재무활동현금흐름",
)

STATEMENT_LABELS = {
    "BS": "재무상태표", "IS": "손익계산서", "CIS": "포괄손익계산서",
    "CF": "현금흐름표", "SCE": "자본변동표",
}


def _won(value: Optional[int]) -> str:
    return f"{value:,}" if value is not None else "–"


def _is_key(account_nm: Optional[str]) -> bool:
    name = (account_nm or "").replace(" ", "")
    return any(k.replace(" ", "") == name for k in KEY_ACCOUNTS)


# ── 조각별 작성 ────────────────────────────────────────────────────

def _overview(company: Company) -> list[str]:
    return [
        f"# {company.corp_name} — {company.audit_year}년 감사 분석자료",
        "",
        f"> 생성일: {date.today().isoformat()}",
        "",
        "| | |",
        "|---|---|",
        f"| DART 고유번호 | {company.corp_code} |",
        f"| 종목코드 | {company.stock_code or '비상장'} |",
        f"| 업종코드 | {company.industry_code or '–'} |",
        f"| 대표자 | {company.ceo_name or '–'} |",
        f"| 결산월 | {company.fiscal_month or '–'}월 |",
        "",
    ]


def _financials(db: Session, company: Company) -> list[str]:
    rows = (
        db.query(FinancialStatement)
        .filter(FinancialStatement.company_id == company.id)
        .order_by(FinancialStatement.fs_div, FinancialStatement.sj_div,
                  FinancialStatement.ord)
        .all()
    )
    if not rows:
        return ["## 재무제표", "", "수집되지 않았습니다.", ""]

    year = rows[0].bsns_year
    out = ["## 재무제표 주요 계정", "", f"사업연도 {year} · 단위 원", ""]

    for fs_div, label in (("CFS", "연결"), ("OFS", "별도")):
        picked = [r for r in rows if r.fs_div == fs_div and _is_key(r.account_nm)]
        if not picked:
            continue

        out += [f"### {label}재무제표", "",
                "| 재무제표 | 계정 | 당기 | 전기 | 전전기 |",
                "|---|---|---:|---:|---:|"]
        for r in picked:
            out.append(
                f"| {STATEMENT_LABELS.get(r.sj_div, r.sj_div)} | {r.account_nm} "
                f"| {_won(r.thstrm_amount)} | {_won(r.frmtrm_amount)} "
                f"| {_won(r.bfefrmtrm_amount)} |"
            )
        out.append("")

    out += ["전 계정은 `01_financials/재무제표_전체.md` 에 있습니다.", ""]
    return out


def _disclosures(db: Session, company: Company) -> list[str]:
    items = (
        db.query(DisclosureItem)
        .filter(DisclosureItem.company_id == company.id)
        .all()
    )
    if not items:
        return []

    counts: dict[str, int] = {}
    for it in items:
        counts[it.category] = counts.get(it.category, 0) + 1

    out = ["## 정기보고서 주요정보", "",
           "사업보고서 시점의 현황이다. 항목별 원본은 `disclosure_items.payload` 에 있다.",
           "", "| 항목 | 건수 |", "|---|---:|"]
    out += [f"| {cat} | {n} |" for cat, n in sorted(counts.items())]
    out.append("")
    return out


def _filings(db: Session, company: Company) -> list[str]:
    rows = (
        db.query(DisclosureFiling)
        .filter(DisclosureFiling.company_id == company.id)
        .order_by(DisclosureFiling.rcept_dt.desc())
        .all()
    )
    if not rows:
        return []

    tagged = [r for r in rows if r.tag]
    out = ["## 기중 공시 이벤트", "",
           f"전체 {len(rows)}건 중 감사 시사점이 붙은 {len(tagged)}건. "
           "미분류는 `disclosure_filings` 에서 볼 수 있다.", ""]

    by_tag: dict[str, list] = {}
    for r in tagged:
        by_tag.setdefault(r.tag, []).append(r)

    for tag in sorted(by_tag, key=lambda t: -len(by_tag[t])):
        out += [f"### {tag} ({len(by_tag[tag])}건)", ""]
        for r in by_tag[tag][:30]:
            out.append(f"- {_date(r.rcept_dt)} {r.report_nm}  \n"
                       f"  <https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r.rcept_no}>")
        if len(by_tag[tag]) > 30:
            out.append(f"- … 외 {len(by_tag[tag]) - 30}건")
        out.append("")

    return out


def _news(db: Session, company: Company) -> list[str]:
    rows = (
        db.query(CompanyNews)
        .filter(CompanyNews.company_id == company.id)
        .order_by(CompanyNews.published_at.desc())
        .all()
    )
    if not rows:
        return []

    tagged = [r for r in rows if r.tag]
    out = ["## 뉴스", "",
           f"전체 {len(rows)}건 중 감사 시사점이 붙은 {len(tagged)}건. "
           "전체 목록은 `02_news/뉴스_전체.md` 에 있다.", ""]

    by_tag: dict[str, list] = {}
    for r in tagged:
        by_tag.setdefault(r.tag, []).append(r)

    for tag in sorted(by_tag, key=lambda t: -len(by_tag[t])):
        out += [f"### {tag} ({len(by_tag[tag])}건)", ""]
        for r in by_tag[tag][:25]:
            line = f"- {r.published_at or '날짜미상'} {r.title}"
            if r.source:
                line += f" ({r.source})"
            out.append(line)
            if r.ai_reason:
                out.append(f"  - {r.ai_reason}")
        if len(by_tag[tag]) > 25:
            out.append(f"- … 외 {len(by_tag[tag]) - 25}건")
        out.append("")

    return out


def _regulatory(db: Session) -> list[str]:
    """중점심사 이슈와 지적사례 — 회사와 무관한 공통 자료."""
    issues = (
        db.query(AuditIssue, FssArticle)
        .join(FssArticle, AuditIssue.article_id == FssArticle.id)
        .order_by(FssArticle.year.desc(), AuditIssue.issue_number)
        .all()
    )
    cases = db.query(FssCaseReport).order_by(FssCaseReport.pub_date.desc()).all()

    out = ["## 규제 중점사항", ""]

    if issues:
        by_year: dict[int, list] = {}
        for issue, article in issues:
            by_year.setdefault(article.year, []).append(issue)

        out += [f"### 금감원 중점심사 회계이슈 ({len(issues)}건)", ""]
        for year in sorted(by_year, reverse=True):
            out += [f"**{year}년**", ""]
            for issue in by_year[year]:
                out.append(f"- {issue.issue_number}. {issue.issue_title}")
                if issue.description:
                    out.append(f"  - {issue.description[:200]}")
            out.append("")
    else:
        out += ["중점심사 이슈가 수집되지 않았습니다.", ""]

    if cases:
        out += [f"### 회계심사·감리 지적사례 ({len(cases)}건)", ""]
        for c in cases:
            mark = "" if c.raw_text else "  ⚠ 본문 미수집"
            out.append(f"- {c.pub_date} {c.title}{mark}")
        out += ["", "사례 본문은 `fss_case_reports.raw_text` 에 있다.", ""]

    return out


def _how_to_dig_deeper() -> list[str]:
    return [
        "---",
        "",
        "## 더 깊이 볼 때",
        "",
        "이 파일은 다이제스트다. 원문이 필요하면 `audit.db` 를 직접 조회한다.",
        "",
        "```sql",
        "-- 특정 지적사례의 본문",
        "SELECT title, raw_text FROM fss_case_reports WHERE title LIKE '%수익%';",
        "",
        "-- 중점심사 보도자료 전문",
        "SELECT year, raw_text FROM fss_articles WHERE year = 2026;",
        "",
        "-- 주요정보 원본 (항목별 컬럼이 달라 JSON 으로 보관)",
        "SELECT category, payload FROM disclosure_items WHERE category = '타법인출자';",
        "",
        "-- 미분류 공시까지 포함한 전체",
        "SELECT rcept_dt, report_nm, tag FROM disclosure_filings ORDER BY rcept_dt DESC;",
        "```",
        "",
        "`raw_text` 는 건당 수만 자다. 필요한 건만 골라 읽을 것.",
        "",
    ]


def _date(value: Optional[str]) -> str:
    if value and len(value) == 8:
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value or ""


# ── 상세 파일 ──────────────────────────────────────────────────────

def _financials_detail(db: Session, company: Company) -> str:
    rows = (
        db.query(FinancialStatement)
        .filter(FinancialStatement.company_id == company.id)
        .order_by(FinancialStatement.fs_div, FinancialStatement.sj_div,
                  FinancialStatement.ord)
        .all()
    )
    out = [f"# {company.corp_name} 재무제표 전 계정", ""]
    if not rows:
        return "\n".join(out + ["수집되지 않았습니다.", ""])

    out += [f"사업연도 {rows[0].bsns_year} · 단위 원", ""]
    current = None
    for r in rows:
        key = (r.fs_div, r.sj_div)
        if key != current:
            current = key
            label = "연결" if r.fs_div == "CFS" else "별도"
            out += ["", f"## {label} · {STATEMENT_LABELS.get(r.sj_div, r.sj_div)}", "",
                    "| 계정 | 당기 | 전기 | 전전기 |", "|---|---:|---:|---:|"]
        name = r.account_nm or ""
        if r.account_detail:
            name += f" · {r.account_detail}"
        out.append(f"| {name} | {_won(r.thstrm_amount)} | {_won(r.frmtrm_amount)} "
                   f"| {_won(r.bfefrmtrm_amount)} |")

    return "\n".join(out) + "\n"


def _news_detail(db: Session, company: Company) -> str:
    rows = (
        db.query(CompanyNews)
        .filter(CompanyNews.company_id == company.id)
        .order_by(CompanyNews.published_at.desc())
        .all()
    )
    out = [f"# {company.corp_name} 뉴스 전체", "",
           f"미분류 포함 {len(rows)}건", ""]
    for r in rows:
        out.append(f"- [{r.tag or '미분류'}] {r.published_at or '날짜미상'} "
                   f"{r.title}" + (f" ({r.source})" if r.source else ""))
        if r.url:
            out.append(f"  - <{r.url}>")
    return "\n".join(out) + "\n"


# ── 진입점 ─────────────────────────────────────────────────────────

def export(db: Session, company: Company) -> dict:
    """작업폴더에 00_INPUT.md 와 상세 파일을 쓴다.

    Returns:
        {"root": str, "files": [상대경로...], "chars": {파일: 글자수}}
    """
    root = Path(company.workspace_path or f"workspace/{company.audit_year}_{company.corp_name}")
    for sub in ("01_financials", "02_news", "03_regulatory", "04_output"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines += _overview(company)
    lines += _financials(db, company)
    lines += _disclosures(db, company)
    lines += _filings(db, company)
    lines += _news(db, company)
    lines += _regulatory(db)
    lines += _how_to_dig_deeper()

    written: dict[str, int] = {}

    def _write(relative: str, text: str) -> None:
        path = root / relative
        path.write_text(text, encoding="utf-8")
        written[relative] = len(text)

    _write("00_INPUT.md", "\n".join(lines))
    _write("01_financials/재무제표_전체.md", _financials_detail(db, company))
    _write("02_news/뉴스_전체.md", _news_detail(db, company))

    logger.info(f"분석자료 내보내기 완료: {root}")
    return {"root": str(root), "files": list(written), "chars": written}
