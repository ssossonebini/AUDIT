"""회사 등록과 재무제표 수집 흐름 검증 (DART 호출은 대역으로 대체)."""

import pytest
from fastapi.testclient import TestClient

from app.core import workspace
from app.crawler import dart_client
from app.db.database import Base, engine, get_db, SessionLocal
from app.main import app

PREFIX = "/api/v1/company"


@pytest.fixture(autouse=True)
def fresh_db_and_workspace(tmp_path, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(workspace, "WORKSPACE_ROOT", tmp_path / "workspace")
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _annual_row(sj_div, name, ord_, thstrm, frmtrm, bfefrmtrm):
    return {
        "sj_div": sj_div, "sj_nm": "재무상태표", "account_nm": name,
        "account_id": f"ifrs-full_{name}", "ord": ord_, "currency": "KRW",
        "thstrm_nm": "제 56 기", "thstrm_amount": thstrm,
        "frmtrm_amount": frmtrm, "bfefrmtrm_amount": bfefrmtrm,
    }


def test_register_company_creates_workspace_folders(client, monkeypatch, tmp_path):
    monkeypatch.setattr(dart_client, "fetch_company", lambda code: {
        "corp_name": "삼성전자", "stock_code": "005930",
        "induty_code": "264", "ceo_nm": "한종희", "acc_mt": "12",
    })

    r = client.post(f"{PREFIX}/companies",
                    json={"corp_code": "00126380", "audit_year": 2026})
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["corp_name"] == "삼성전자"
    assert body["industry_code"] == "264"

    root = tmp_path / "workspace" / "2026_삼성전자"
    assert root.is_dir()
    for sub in ("01_financials", "02_news", "03_regulatory", "04_output"):
        assert (root / sub).is_dir(), f"{sub} 가 만들어지지 않았습니다"


def test_registering_the_same_corp_code_twice_is_rejected(client, monkeypatch):
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "삼성전자"})
    payload = {"corp_code": "00126380", "audit_year": 2026}

    assert client.post(f"{PREFIX}/companies", json=payload).status_code == 200
    assert client.post(f"{PREFIX}/companies", json=payload).status_code == 409


def test_collect_financials_stores_three_years_from_one_call(client, monkeypatch):
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "삼성전자"})
    calls = []

    def fake_fetch(corp_code, year, fs_div="CFS", reprt_code=None):
        calls.append((year, fs_div))
        return [
            _annual_row("BS", "자산총계", 1, "3,000", "2,000", "1,000"),
            _annual_row("IS", "매출액", 2, "5,000", "4,500", "4,000"),
        ]

    monkeypatch.setattr(dart_client, "fetch_financials", fake_fetch)

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00126380", "audit_year": 2026}).json()

    r = client.post(f"{PREFIX}/companies/{created['id']}/financials")
    assert r.status_code == 200, r.text
    summary = r.json()

    # 감사대상연도(2026)의 사업보고서는 아직 없으므로 직전 연도를 쓴다
    assert summary["bsns_year"] == 2025
    assert calls == [(2025, "CFS")], "연도별로 세 번 호출하면 안 된다"

    lines = client.get(f"{PREFIX}/companies/{created['id']}/financials").json()
    assets = next(x for x in lines if x["account_nm"] == "자산총계")
    assert (assets["thstrm_amount"], assets["frmtrm_amount"],
            assets["bfefrmtrm_amount"]) == (3000, 2000, 1000)


def test_collect_falls_back_to_separate_statements(client, monkeypatch):
    """종속기업이 없으면 연결재무제표가 없다. 개별로 내려가야 한다."""
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "비상장회사"})
    seen = []

    def fake_fetch(corp_code, year, fs_div="CFS", reprt_code=None):
        seen.append(fs_div)
        if fs_div == "CFS":
            raise dart_client.DartError("013")
        return [_annual_row("BS", "자산총계", 1, "100", "90", "80")]

    monkeypatch.setattr(dart_client, "fetch_financials", fake_fetch)

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00999999", "audit_year": 2026}).json()
    r = client.post(f"{PREFIX}/companies/{created['id']}/financials")

    assert r.status_code == 200, r.text
    assert r.json()["fs_div"] == "OFS"
    assert seen == ["CFS", "OFS"]


def test_recollecting_a_year_replaces_rather_than_duplicates(client, monkeypatch):
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "삼성전자"})
    monkeypatch.setattr(dart_client, "fetch_financials",
                        lambda *a, **k: [_annual_row("BS", "자산총계", 1, "1", "2", "3")])

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00126380", "audit_year": 2026}).json()

    client.post(f"{PREFIX}/companies/{created['id']}/financials")
    client.post(f"{PREFIX}/companies/{created['id']}/financials")

    lines = client.get(f"{PREFIX}/companies/{created['id']}/financials").json()
    assert len(lines) == 1, "재수집이 행을 중복 적재했습니다"


def test_collect_rejects_years_before_dart_coverage(client, monkeypatch):
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "옛날회사"})
    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00111111", "audit_year": 2026}).json()

    r = client.post(f"{PREFIX}/companies/{created['id']}/financials",
                    params={"bsns_year": 2010})
    assert r.status_code == 400
    assert "2015" in r.json()["detail"]


def test_missing_api_key_is_reported_as_unavailable(client, monkeypatch):
    def no_key(*a, **k):
        raise dart_client.DartError("010", "DART_API_KEY가 .env에 설정되지 않았습니다.")

    monkeypatch.setattr(dart_client, "fetch_company", no_key)
    r = client.post(f"{PREFIX}/companies",
                    json={"corp_code": "00126380", "audit_year": 2026})

    assert r.status_code == 503
    assert "DART_API_KEY" in r.json()["detail"]


def test_deleting_a_company_keeps_the_workspace_folder(client, monkeypatch, tmp_path):
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "삼성전자"})
    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00126380", "audit_year": 2026}).json()

    assert client.delete(f"{PREFIX}/companies/{created['id']}").status_code == 200
    assert (tmp_path / "workspace" / "2026_삼성전자").is_dir(), \
        "수집한 자료가 든 폴더를 지우면 안 됩니다"


def test_workspace_name_is_safe_for_windows():
    assert "/" not in workspace.safe_name("A/B 주식회사")
    assert ":" not in workspace.safe_name("A:B")
    assert workspace.folder_name(2026, "삼성 전자") == "2026_삼성_전자"
