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


def test_collect_financials_stores_both_divisions_for_one_year(client, monkeypatch):
    """연결과 별도를 모두 받아야 한다. 감사 대상은 별도인 경우가 많다."""
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "삼성전자"})
    calls = []

    def fake_fetch(corp_code, year, fs_div="CFS", reprt_code=None):
        calls.append((year, fs_div))
        base = 3000 if fs_div == "CFS" else 1500
        return [_annual_row("BS", "자산총계", 1, str(base), "2,000", "1,000")]

    monkeypatch.setattr(dart_client, "fetch_financials", fake_fetch)

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00126380", "audit_year": 2026}).json()

    r = client.post(f"{PREFIX}/companies/{created['id']}/financials")
    assert r.status_code == 200, r.text
    summary = r.json()

    # 감사대상연도(2026)의 사업보고서는 아직 없으므로 직전 연도를 쓴다
    assert summary["bsns_year"] == 2025
    # 연도별로 반복 호출하지 않는다 — 구분별로 한 번씩만
    assert calls == [(2025, "CFS"), (2025, "OFS")]
    assert {c["fs_div"] for c in summary["collected"]} == {"CFS", "OFS"}

    lines = client.get(f"{PREFIX}/companies/{created['id']}/financials").json()
    assert {l["fs_div"] for l in lines} == {"CFS", "OFS"}


def test_financials_can_be_filtered_by_division(client, monkeypatch):
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "삼성전자"})

    def fake_fetch(corp_code, year, fs_div="CFS", reprt_code=None):
        amount = "3,000" if fs_div == "CFS" else "1,500"
        return [_annual_row("BS", "자산총계", 1, amount, "2,000", "1,000")]

    monkeypatch.setattr(dart_client, "fetch_financials", fake_fetch)
    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00126380", "audit_year": 2026}).json()
    client.post(f"{PREFIX}/companies/{created['id']}/financials")

    separate = client.get(f"{PREFIX}/companies/{created['id']}/financials",
                          params={"fs_div": "OFS"}).json()
    assert len(separate) == 1
    assert separate[0]["thstrm_amount"] == 1500


def test_collect_keeps_going_when_one_division_is_absent(client, monkeypatch):
    """종속기업이 없으면 연결재무제표를 제출하지 않는다. 별도만 저장하면 된다."""
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
    body = r.json()
    assert [c["fs_div"] for c in body["collected"]] == ["OFS"]
    assert "공시되지 않았습니다" in body["message"]
    assert seen == ["CFS", "OFS"]


def test_collect_reports_a_real_dart_error_instead_of_swallowing_it(client, monkeypatch):
    """013(데이터 없음)이 아닌 오류는 삼키면 안 된다 — 한도 초과 등."""
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "삼성전자"})

    def over_limit(corp_code, year, fs_div="CFS", reprt_code=None):
        raise dart_client.DartError("020")

    monkeypatch.setattr(dart_client, "fetch_financials", over_limit)
    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00126380", "audit_year": 2026}).json()

    r = client.post(f"{PREFIX}/companies/{created['id']}/financials")
    assert r.status_code == 502
    assert "요청 제한" in r.json()["detail"]


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
    assert len(lines) == 2, "재수집이 행을 중복 적재했습니다"   # 연결 1 + 별도 1


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


# ── 정기보고서 주요정보 ────────────────────────────────────────────

def _register(client, monkeypatch, name="삼성전자", code="00126380", year=2026):
    monkeypatch.setattr(dart_client, "fetch_company", lambda c: {"corp_name": name})
    return client.post(f"{PREFIX}/companies",
                       json={"corp_code": code, "audit_year": year}).json()


def test_target_years_span_the_reports_filed_in_the_window():
    """직전 회계연도 개시일~오늘 창에는 사업보고서 두 해분이 들어온다."""
    from datetime import date as _date
    assert dart_client.target_business_years(_date(2026, 8, 26)) == [2024, 2025]
    assert dart_client.target_business_years(_date(2027, 1, 2)) == [2025, 2026]


def test_collect_disclosures_gathers_every_category(client, monkeypatch):
    created = _register(client, monkeypatch)
    seen = []

    def fake(corp_code, year, api_file, reprt_code=None):
        seen.append((api_file, year))
        return [{"rcept_no": f"2026{year}", "se": "보통주", "thstrm": "1,000"}]

    monkeypatch.setattr(dart_client, "fetch_major_info", fake)

    r = client.post(f"{PREFIX}/companies/{created['id']}/disclosures")
    assert r.status_code == 200, r.text
    body = r.json()

    assert {c["category"] for c in body["collected"]} == set(dart_client.MAJOR_INFO_APIS)
    # 항목 8종 × 사업연도 2개
    assert len(seen) == len(dart_client.MAJOR_INFO_APIS) * 2
    assert body["total_rows"] == len(dart_client.MAJOR_INFO_APIS) * 2


def test_payload_keeps_the_raw_response_row(client, monkeypatch):
    """응답 스키마가 항목마다 달라 payload 를 그대로 보관한다."""
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_major_info",
                        lambda *a, **k: [{"rcept_no": "1", "stock_knd": "보통주",
                                          "thstrm": "1,500", "frmtrm": "1,200"}])

    client.post(f"{PREFIX}/companies/{created['id']}/disclosures",
                params={"bsns_year": 2025})
    rows = client.get(f"{PREFIX}/companies/{created['id']}/disclosures",
                      params={"category": "배당"}).json()

    assert rows[0]["payload"]["stock_knd"] == "보통주"
    assert rows[0]["payload"]["thstrm"] == "1,500"


def test_one_failing_category_does_not_abort_the_rest(client, monkeypatch):
    """항목 하나가 막혀도 나머지는 모아야 한다."""
    created = _register(client, monkeypatch)

    def flaky(corp_code, year, api_file, reprt_code=None):
        if api_file.startswith("alotMatter"):
            raise dart_client.DartError("800")     # 시스템 점검
        return [{"rcept_no": "1"}]

    monkeypatch.setattr(dart_client, "fetch_major_info", flaky)
    body = client.post(f"{PREFIX}/companies/{created['id']}/disclosures").json()

    failed = [c for c in body["collected"] if c["error"]]
    assert [c["category"] for c in failed] == ["배당"]
    assert body["total_rows"] > 0, "한 항목 실패로 전체가 비면 안 된다"
    assert "실패" in body["message"]


def test_absent_category_is_not_treated_as_an_error(client, monkeypatch):
    """배당을 하지 않은 회사는 013 이 온다. 오류가 아니다."""
    created = _register(client, monkeypatch)

    def none_found(corp_code, year, api_file, reprt_code=None):
        raise dart_client.DartError("013")

    monkeypatch.setattr(dart_client, "fetch_major_info", none_found)
    body = client.post(f"{PREFIX}/companies/{created['id']}/disclosures").json()

    assert body["total_rows"] == 0
    assert all(c["error"] is None for c in body["collected"])


def test_recollecting_replaces_rows_for_the_same_year(client, monkeypatch):
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_major_info",
                        lambda *a, **k: [{"rcept_no": "1"}])

    client.post(f"{PREFIX}/companies/{created['id']}/disclosures", params={"bsns_year": 2025})
    client.post(f"{PREFIX}/companies/{created['id']}/disclosures", params={"bsns_year": 2025})

    rows = client.get(f"{PREFIX}/companies/{created['id']}/disclosures").json()
    assert len(rows) == len(dart_client.MAJOR_INFO_APIS), "재수집이 중복 적재했습니다"


def test_disclosure_flag_appears_on_the_company_list(client, monkeypatch):
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_major_info",
                        lambda *a, **k: [{"rcept_no": "1"}])

    before = client.get(f"{PREFIX}/companies").json()[0]
    assert before["has_disclosures"] is False

    client.post(f"{PREFIX}/companies/{created['id']}/disclosures")
    after = client.get(f"{PREFIX}/companies").json()[0]
    assert after["has_disclosures"] is True
