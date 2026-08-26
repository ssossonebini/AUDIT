"""분석자료 내보내기 검증.

가장 중요한 성질은 하나다 — **raw_text 가 출력에 새어나가면 안 된다.**
수집한 PDF 전문을 전부 펼치면 45만 토큰이 넘어 컨텍스트에 들어가지 않는다.
"""

import pytest
from fastapi.testclient import TestClient

from app.core import exporter, workspace
from app.crawler import dart_client
from app.db.database import Base, SessionLocal, engine
from app.db.models import (
    AuditIssue, Company, CompanyNews, DisclosureFiling, DisclosureItem,
    FinancialStatement, FssArticle, FssCaseReport,
)
from app.main import app

PREFIX = "/api/v1/company"
SECRET = "PDF 전문에만 있어야 하는 문장입니다"


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(workspace, "WORKSPACE_ROOT", tmp_path / "workspace")
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seeded(tmp_path):
    """회사 하나에 각 자료를 조금씩 심어둔다."""
    db = SessionLocal()
    root = tmp_path / "workspace" / "2026_테스트회사"

    company = Company(
        corp_code="00100000", corp_name="테스트회사", stock_code="000000",
        industry_code="264", ceo_name="홍길동", fiscal_month="12",
        audit_year=2026, workspace_path=str(root),
    )
    db.add(company)
    db.flush()

    db.add_all([
        FinancialStatement(
            company_id=company.id, bsns_year=2025, fs_div="CFS", sj_div="BS",
            account_nm="자산총계", ord=1, currency="KRW", thstrm_nm="제 10 기",
            thstrm_amount=3000, frmtrm_amount=2000, bfefrmtrm_amount=1000,
        ),
        FinancialStatement(
            company_id=company.id, bsns_year=2025, fs_div="CFS", sj_div="BS",
            account_nm="현금및현금성자산", ord=2, currency="KRW",
            thstrm_amount=500, frmtrm_amount=400, bfefrmtrm_amount=300,
        ),
        DisclosureItem(
            company_id=company.id, category="배당", bsns_year=2025,
            payload='{"se": "보통주", "thstrm": "1,000"}',
        ),
        DisclosureFiling(
            company_id=company.id, rcept_no="202608210001",
            report_nm="주요사항보고서(자기주식취득결정)",
            rcept_dt="20260821", pblntf_ty="B", tag="자본거래",
        ),
        DisclosureFiling(
            company_id=company.id, rcept_no="202608210002",
            report_nm="기타경영사항(자율공시)",
            rcept_dt="20260820", pblntf_ty="I", tag=None,
        ),
        CompanyNews(
            company_id=company.id, title="테스트회사 4분기 영업이익 급감",
            published_at="2026-08-25", source="한국경제",
            tag="재무·실적", ai_reason="실적 악화로 계속기업 검토 필요",
        ),
        CompanyNews(
            company_id=company.id, title="테스트회사 신제품 출시",
            published_at="2026-08-20", source="매일경제", tag=None,
        ),
        FssCaseReport(
            ntt_id="1", title="2025년 지적사례", pub_date="2025-12-02",
            year=2025, raw_text=SECRET,
        ),
    ])

    article = FssArticle(ntt_id="a1", title="2026 중점심사", year=2026, raw_text=SECRET)
    db.add(article)
    db.flush()
    db.add(AuditIssue(
        article_id=article.id, issue_number=1,
        issue_title="수익인식", description="계약 식별과 수행의무 배분",
    ))

    db.commit()
    db.refresh(company)
    yield company, db, root
    db.close()


def _read(root, name):
    return (root / name).read_text(encoding="utf-8")


# ── 핵심 성질 ──────────────────────────────────────────────────────

def test_raw_text_never_reaches_any_exported_file(seeded):
    """PDF 전문을 덤프하면 컨텍스트에 들어가지 않는다."""
    company, db, root = seeded
    result = exporter.export(db, company)

    for relative in result["files"]:
        content = (root / relative).read_text(encoding="utf-8")
        assert SECRET not in content, f"{relative} 에 raw_text 가 새어나갔습니다"


def test_entry_file_points_at_the_database_for_originals(seeded):
    company, db, root = seeded
    exporter.export(db, company)
    text = _read(root, "00_INPUT.md")

    assert "audit.db" in text
    assert "raw_text" in text, "원문을 어디서 찾는지 알려줘야 한다"


# ── 내용 ───────────────────────────────────────────────────────────

def test_entry_file_carries_company_and_key_accounts(seeded):
    company, db, root = seeded
    exporter.export(db, company)
    text = _read(root, "00_INPUT.md")

    assert "테스트회사" in text
    assert "자산총계" in text
    assert "3,000" in text and "1,000" in text     # 당기·전전기


def test_non_key_accounts_are_left_to_the_detail_file(seeded):
    """00_INPUT.md 는 다이제스트다. 전 계정은 하위 파일에 둔다."""
    company, db, root = seeded
    exporter.export(db, company)

    assert "현금및현금성자산" not in _read(root, "00_INPUT.md")
    assert "현금및현금성자산" in _read(root, "01_financials/재무제표_전체.md")


def test_tagged_filings_and_news_are_grouped_by_tag(seeded):
    company, db, root = seeded
    exporter.export(db, company)
    text = _read(root, "00_INPUT.md")

    assert "자본거래" in text
    assert "자기주식취득결정" in text
    assert "재무·실적" in text
    assert "계속기업 검토 필요" in text


def test_untagged_items_are_not_dropped_from_the_detail_file(seeded):
    """규칙에 안 걸린 것도 사람이 볼 수 있어야 한다."""
    company, db, root = seeded
    exporter.export(db, company)

    assert "신제품 출시" in _read(root, "02_news/뉴스_전체.md")


def test_regulatory_section_lists_issues_and_cases(seeded):
    company, db, root = seeded
    exporter.export(db, company)
    text = _read(root, "00_INPUT.md")

    assert "수익인식" in text
    assert "수행의무 배분" in text
    assert "2025년 지적사례" in text


def test_filings_link_to_the_dart_original(seeded):
    company, db, root = seeded
    exporter.export(db, company)
    assert "rcpNo=202608210001" in _read(root, "00_INPUT.md")


# ── 파일·폴더 ──────────────────────────────────────────────────────

def test_export_creates_the_workspace_subfolders(seeded):
    company, db, root = seeded
    exporter.export(db, company)

    for sub in ("01_financials", "02_news", "03_regulatory", "04_output"):
        assert (root / sub).is_dir()


def test_export_is_idempotent(seeded):
    company, db, root = seeded
    exporter.export(db, company)
    first = _read(root, "00_INPUT.md")
    exporter.export(db, company)

    assert _read(root, "00_INPUT.md") == first


def test_export_works_when_nothing_has_been_collected(tmp_path):
    """수집 전에 눌러도 죽지 않고 '수집되지 않았습니다' 로 남아야 한다."""
    db = SessionLocal()
    root = tmp_path / "workspace" / "2026_빈회사"
    company = Company(corp_code="00200000", corp_name="빈회사",
                      audit_year=2026, workspace_path=str(root))
    db.add(company)
    db.commit()
    db.refresh(company)

    result = exporter.export(db, company)
    text = (root / "00_INPUT.md").read_text(encoding="utf-8")

    assert "빈회사" in text
    assert "수집되지 않았습니다" in text
    assert len(result["files"]) == 3
    db.close()


# ── 라우트 ─────────────────────────────────────────────────────────

def test_export_endpoint_reports_the_entry_file_size(seeded):
    company, db, root = seeded
    client = TestClient(app)

    r = client.post(f"{PREFIX}/companies/{company.id}/export")
    assert r.status_code == 200, r.text
    body = r.json()

    assert "00_INPUT.md" in body["files"]
    assert body["approx_tokens"] > 0
    assert "토큰" in body["message"]


def test_export_endpoint_404s_for_an_unknown_company():
    client = TestClient(app)
    assert client.post(f"{PREFIX}/companies/9999/export").status_code == 404
