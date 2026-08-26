"""회사 등록과 재무제표 수집 흐름 검증 (DART 호출은 대역으로 대체)."""

import pathlib
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core import workspace
from app.crawler import dart_client
from app.db.database import Base, engine, get_db, SessionLocal
from app.main import app

PREFIX = "/api/v1/company"


def _refuse_to_touch_the_real_db():
    """drop_all 을 부르기 전에 대상이 실제 DB가 아닌지 확인한다.

    conftest.py 가 임시 DB로 돌려놓지만, 그것 하나에 기대지 않는다.
    한 번 실수로 수집 데이터를 전부 날린 적이 있다.
    """
    from app.db.database import DEFAULT_DATABASE_URL

    target = pathlib.Path(str(engine.url).replace("sqlite:///", "")).resolve()
    real = pathlib.Path(DEFAULT_DATABASE_URL.replace("sqlite:///", "")).resolve()
    if target == real:
        raise RuntimeError(f"실제 DB를 지우려 했습니다: {target}")


@pytest.fixture(autouse=True)
def fresh_db_and_workspace(tmp_path, monkeypatch):
    _refuse_to_touch_the_real_db()
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


def test_target_years_cover_this_year_and_the_prior_calendar_year():
    """2026년 기말감사 기준: 2026년 기중 공시 + 2025년 1역년 공시.

    사업보고서는 사업연도 종료 후 90일 안에 제출되므로
      2026년 기중 공시  → 2026-03 제출된 FY2025 사업보고서
      2025년 1역년 공시 → 2025-03 제출된 FY2024 사업보고서
    두 창을 합치면 사업연도 2024·2025 가 대상이 된다.
    """
    assert dart_client.target_business_years(date(2026, 8, 26)) == [2024, 2025]

    # 감사연도가 바뀌면 한 해씩 밀린다
    assert dart_client.target_business_years(date(2027, 6, 1)) == [2025, 2026]


def test_target_years_still_ask_for_the_year_not_yet_filed():
    """1~3월에는 직전 사업연도 보고서가 아직 없다.

    그래도 요청은 한다 — 없으면 013 이 오고 빈 항목으로 기록되므로,
    제출 시점을 코드가 추측하는 것보다 안전하다.
    """
    assert dart_client.target_business_years(date(2026, 1, 15)) == [2024, 2025]


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


# ── 공시 목록 (기중 이벤트) ────────────────────────────────────────

def _filing(rcept_no, report_nm, ty="B", dt="20260821"):
    return {"rcept_no": rcept_no, "report_nm": report_nm, "flr_nm": "삼성전자",
            "rcept_dt": dt, "pblntf_ty": ty, "rm": ""}


def test_fiscal_window_covers_prior_calendar_year_through_today():
    """2026년 기말감사: 2025년 1역년 + 2026년 기중."""
    assert dart_client.fiscal_window(date(2026, 8, 26)) == ("20250101", "20260826")


def test_tags_match_the_report_names_dart_actually_uses():
    t = dart_client.tag_filing
    assert t("주요사항보고서(자기주식취득결정)") == "자본거래"
    assert t("동일인등출자계열회사와의상품·용역거래변경") == "특수관계자"
    assert t("주요사항보고서(회사합병결정)") == "사업결합"
    assert t("감사보고서제출") == "외부감사"
    assert t("반기보고서 (2026.06)") == "정기보고서"
    assert t("기타경영사항(자율공시)") is None      # 규칙 밖은 미분류로 남긴다


def test_collect_filings_covers_mid_year_events(client, monkeypatch):
    """2단계(사업보고서 현황)로는 안 잡히는 기중 결정이 여기서 잡혀야 한다."""
    created = _register(client, monkeypatch)
    windows = []

    def fake(corp_code, bgn_de, end_de, pblntf_ty=None, max_pages=20):
        windows.append((bgn_de, end_de, pblntf_ty))
        if pblntf_ty == "B":
            return [_filing("202608210001", "주요사항보고서(자기주식취득결정)")]
        if pblntf_ty == "J":
            return [_filing("202608140002", "동일인등출자계열회사와의상품·용역거래변경", "J", "20260814")]
        return []

    monkeypatch.setattr(dart_client, "fetch_disclosure_list", fake)
    r = client.post(f"{PREFIX}/companies/{created['id']}/filings")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["total_rows"] == 2
    assert body["by_tag"] == {"자본거래": 1, "특수관계자": 1}
    # 감사 관련 네 유형을 같은 창으로 조회한다
    assert [w[2] for w in windows] == list(dart_client.DEFAULT_PUBLIC_TYPES)
    assert {(w[0], w[1]) for w in windows} == {dart_client.fiscal_window(date.today())}

    rows = client.get(f"{PREFIX}/companies/{created['id']}/filings").json()
    treasury = next(r for r in rows if "자기주식" in r["report_nm"])
    assert treasury["dart_url"].endswith("rcpNo=202608210001")


def test_same_filing_listed_under_two_types_is_stored_once(client, monkeypatch):
    """공시 하나가 여러 유형으로 잡히기도 한다."""
    created = _register(client, monkeypatch)
    monkeypatch.setattr(
        dart_client, "fetch_disclosure_list",
        lambda *a, **k: [_filing("202608210001", "주요사항보고서(자기주식취득결정)")],
    )

    body = client.post(f"{PREFIX}/companies/{created['id']}/filings").json()
    assert body["total_rows"] == 1, "접수번호가 같은 공시가 중복 저장됐습니다"


def test_untagged_filings_are_kept_and_counted(client, monkeypatch):
    """규칙에 안 걸려도 버리지 않는다 — 사람이 볼 수 있어야 한다."""
    created = _register(client, monkeypatch)
    monkeypatch.setattr(
        dart_client, "fetch_disclosure_list",
        lambda *a, **k: [_filing("1", "기타경영사항(자율공시)", "I")],
    )

    body = client.post(f"{PREFIX}/companies/{created['id']}/filings").json()
    assert body["untagged"] == 1
    assert len(client.get(f"{PREFIX}/companies/{created['id']}/filings").json()) == 1


def test_filings_can_be_filtered_by_tag(client, monkeypatch):
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [
        _filing("1", "주요사항보고서(자기주식취득결정)"),
        _filing("2", "주요사항보고서(회사합병결정)"),
    ])
    client.post(f"{PREFIX}/companies/{created['id']}/filings")

    rows = client.get(f"{PREFIX}/companies/{created['id']}/filings",
                      params={"tag": "사업결합"}).json()
    assert len(rows) == 1 and "합병" in rows[0]["report_nm"]


def test_recollecting_filings_replaces_the_previous_set(client, monkeypatch):
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list",
                        lambda *a, **k: [_filing("1", "주요사항보고서(자기주식취득결정)")])

    client.post(f"{PREFIX}/companies/{created['id']}/filings")
    client.post(f"{PREFIX}/companies/{created['id']}/filings")

    rows = client.get(f"{PREFIX}/companies/{created['id']}/filings").json()
    assert len(rows) == 1


# ── 사업보고서 원문 ────────────────────────────────────────────────

def _annual(rcept_no, report_nm, rcept_dt):
    return {"rcept_no": rcept_no, "report_nm": report_nm,
            "rcept_dt": rcept_dt, "flr_nm": "삼성전자", "pblntf_ty": "A"}


def test_sections_do_not_require_disclosures_to_be_collected_first(client, monkeypatch):
    """수집 순서에 매이면 안 된다 — 화면 버튼 순서를 바꾸면 바로 깨진다."""
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [
        _annual("20260310002820", "사업보고서 (2025.12)", "20260310"),
    ])
    from app.crawler import dart_document
    monkeypatch.setattr(dart_document, "fetch_document",
                        lambda rcept_no: {"20260310002820.xml": "<DOCUMENT/>"})

    r = client.post(f"{PREFIX}/companies/{created['id']}/sections")
    assert r.status_code == 200, r.text
    assert r.json()["rcept_no"] == "20260310002820"


def test_annual_report_is_chosen_over_half_year_and_quarterly(client, monkeypatch):
    """정기공시에는 반기·분기보고서가 섞여 온다."""
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [
        _annual("2", "반기보고서 (2026.06)", "20260814"),
        _annual("1", "사업보고서 (2025.12)", "20260310"),
        _annual("3", "분기보고서 (2026.03)", "20260515"),
    ])
    from app.crawler import dart_document
    monkeypatch.setattr(dart_document, "fetch_document",
                        lambda rcept_no: {f"{rcept_no}.xml": "<DOCUMENT/>"})

    body = client.post(f"{PREFIX}/companies/{created['id']}/sections").json()
    assert body["rcept_no"] == "1"
    assert body["bsns_year"] == 2025


def test_the_latest_correction_of_an_annual_report_wins(client, monkeypatch):
    """[기재정정] 본이 원본보다 나중에 접수된다."""
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [
        _annual("1", "사업보고서 (2025.12)", "20260310"),
        _annual("2", "[기재정정]사업보고서 (2025.12)", "20260420"),
    ])
    from app.crawler import dart_document
    monkeypatch.setattr(dart_document, "fetch_document",
                        lambda rcept_no: {f"{rcept_no}.xml": "<DOCUMENT/>"})

    assert client.post(f"{PREFIX}/companies/{created['id']}/sections").json()["rcept_no"] == "2"


def test_missing_annual_report_is_reported_clearly(client, monkeypatch):
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [])

    r = client.post(f"{PREFIX}/companies/{created['id']}/sections")
    assert r.status_code == 404
    assert "사업보고서" in r.json()["detail"]


def test_retag_updates_flags_without_refetching(client, monkeypatch):
    """키워드 목록이 바뀌었다고 8MB 를 다시 받을 이유는 없다."""
    from app.crawler import dart_document
    from app.db.models import ReportSection

    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [
        _annual("1", "사업보고서 (2025.12)", "20260310"),
    ])

    xml = ("<DOCUMENT><BODY><SECTION-1><TITLE>III. 재무</TITLE>"
           "<SECTION-2><TITLE>10. 투자부동산</TITLE><P>내용</P></SECTION-2>"
           "</SECTION-1></BODY></DOCUMENT>")
    monkeypatch.setattr(dart_document, "fetch_document", lambda r: {"1.xml": xml})
    client.post(f"{PREFIX}/companies/{created['id']}/sections")

    # 저장 시점에 표시가 없었던 상태를 만든다
    db = SessionLocal()
    for row in db.query(ReportSection).all():
        row.audit_relevant = False
    db.commit()
    db.close()

    calls = []
    monkeypatch.setattr(dart_document, "fetch_document",
                        lambda r: calls.append(r) or {})

    r = client.post(f"{PREFIX}/companies/{created['id']}/sections/retag")
    assert r.status_code == 200, r.text
    body = r.json()

    assert calls == [], "재태깅이 원문을 다시 내려받았습니다"
    assert "10. 투자부동산" in body["added"]
    assert body["audit_relevant"] >= 1


def test_retag_without_collected_sections_is_reported(client, monkeypatch):
    created = _register(client, monkeypatch)
    r = client.post(f"{PREFIX}/companies/{created['id']}/sections/retag")

    assert r.status_code == 404
    assert "원문 수집" in r.json()["detail"]


# ── 전기말 사업보고서 + 당기중 최신 분·반기보고서 ────────────────────
#
# 사업보고서만 보면 기말(2025-12-31)에 멈춘 숫자로 2026년 기말감사 위험을
# 평가하게 된다. 유동비율이 반기에 어디까지 갔는지가 계속기업 판단의 핵심인데
# 그걸 볼 수 없다. 반대로 중간보고서만 보면 3개년 비교와 완전한 주석을 잃는다.

def _periodic_list(*names):
    """정기공시(A) 목록 대역. (보고서명, 접수일, 접수번호)"""
    return [
        {"report_nm": nm, "rcept_dt": dt, "rcept_no": no, "flr_nm": "회사",
         "corp_name": "테스트", "corp_code": "00000000"}
        for nm, dt, no in names
    ]


def _quarter_row(sj_div, name, ord_, add, prior_add, prior_q):
    """분기·반기 응답. 손익은 3개월과 누적이 따로 온다."""
    return {
        "sj_div": sj_div, "sj_nm": "손익계산서", "account_nm": name,
        "account_id": f"ifrs-full_{name}", "ord": ord_, "currency": "KRW",
        "thstrm_nm": "제 76 기 반기", "thstrm_amount": "1",   # 3개월분
        "thstrm_add_amount": add,
        "frmtrm_q_amount": prior_q, "frmtrm_add_amount": prior_add,
    }


@pytest.fixture
def periodic(monkeypatch):
    """2025 사업보고서와 2026 반기보고서가 공시된 회사."""
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "(주)영풍", "acc_mt": "12"})
    monkeypatch.setattr(dart_client, "fetch_disclosure_list",
                        lambda *a, **k: _periodic_list(
                            ("반기보고서 (2026.06)", "20260814", "BBB"),
                            ("사업보고서 (2025.12)", "20260317", "AAA"),
                            ("분기보고서 (2025.09)", "20251114", "OLD"),
                        ))


def test_both_the_annual_and_the_latest_interim_are_collected(client, periodic, monkeypatch):
    asked = []

    def fake_fetch(corp_code, year, fs_div="CFS", reprt_code=None):
        asked.append((year, reprt_code, fs_div))
        if fs_div == "OFS":
            raise dart_client.DartError("013")
        return [_annual_row("BS", "자산총계", 1, "100", "90", "80")]

    monkeypatch.setattr(dart_client, "fetch_financials", fake_fetch)

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00141307", "audit_year": 2026}).json()
    r = client.post(f"{PREFIX}/companies/{created['id']}/financials")
    assert r.status_code == 200, r.text

    got = {(y, c) for y, c, _ in asked}
    assert (2025, "11011") in got, "전기말 사업보고서를 받지 않았습니다"
    assert (2026, "11012") in got, "당기 반기보고서를 받지 않았습니다"

    reports = {(x["bsns_year"], x["reprt_code"]) for x in r.json()["reports"]}
    assert reports == {(2025, "11011"), (2026, "11012")}


def test_an_interim_older_than_the_annual_is_ignored(client, monkeypatch):
    """2025년 3분기는 2025 사업보고서에 이미 흡수됐다. 다시 받을 이유가 없다."""
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "회사", "acc_mt": "12"})
    monkeypatch.setattr(dart_client, "fetch_disclosure_list",
                        lambda *a, **k: _periodic_list(
                            ("사업보고서 (2025.12)", "20260317", "AAA"),
                            ("분기보고서 (2025.09)", "20251114", "OLD"),
                        ))
    asked = []
    monkeypatch.setattr(dart_client, "fetch_financials",
                        lambda c, y, fs_div="CFS", reprt_code=None:
                        (asked.append((y, reprt_code)) or
                         [_annual_row("BS", "자산총계", 1, "100", "90", "80")]))

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00000001", "audit_year": 2026}).json()
    client.post(f"{PREFIX}/companies/{created['id']}/financials")

    assert {c for _, c in asked} == {"11011"}


def test_the_half_year_does_not_erase_the_annual(client, periodic, monkeypatch):
    """삭제 조건에 reprt_code 가 빠지면 나중에 받은 쪽이 앞의 것을 지운다."""
    def fake_fetch(corp_code, year, fs_div="CFS", reprt_code=None):
        if fs_div == "OFS":
            raise dart_client.DartError("013")
        if reprt_code == dart_client.REPRT_ANNUAL:
            return [_annual_row("BS", "자산총계", 1, "100", "90", "80")]
        return [_quarter_row("IS", "매출액", 1, "50", "40", "20")]

    monkeypatch.setattr(dart_client, "fetch_financials", fake_fetch)

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00141307", "audit_year": 2026}).json()
    client.post(f"{PREFIX}/companies/{created['id']}/financials")

    rows = client.get(f"{PREFIX}/companies/{created['id']}/financials").json()
    codes = {r["reprt_code"] for r in rows}
    assert codes == {"11011", "11012"}, f"보고서가 서로를 지웠습니다: {codes}"


def test_recollecting_replaces_only_the_same_report(client, periodic, monkeypatch):
    monkeypatch.setattr(
        dart_client, "fetch_financials",
        lambda c, y, fs_div="CFS", reprt_code=None:
        [] if fs_div == "OFS" else [_annual_row("BS", "자산총계", 1, "100", "90", "80")])

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00141307", "audit_year": 2026}).json()
    client.post(f"{PREFIX}/companies/{created['id']}/financials")
    first = len(client.get(f"{PREFIX}/companies/{created['id']}/financials").json())

    client.post(f"{PREFIX}/companies/{created['id']}/financials")
    again = len(client.get(f"{PREFIX}/companies/{created['id']}/financials").json())

    assert first == again, "다시 수집하니 행이 늘었습니다"


def test_interim_income_is_stored_on_a_cumulative_basis(client, periodic, monkeypatch):
    """당기를 누적으로 읽고 전기를 3개월로 읽으면 전년 동기 대비가 어긋난다."""
    def fake_fetch(corp_code, year, fs_div="CFS", reprt_code=None):
        if fs_div == "OFS":
            raise dart_client.DartError("013")
        if reprt_code == dart_client.REPRT_ANNUAL:
            return []
        return [_quarter_row("IS", "매출액", 1, "50", "40", "20")]

    monkeypatch.setattr(dart_client, "fetch_financials", fake_fetch)

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00141307", "audit_year": 2026}).json()
    client.post(f"{PREFIX}/companies/{created['id']}/financials")

    rows = client.get(f"{PREFIX}/companies/{created['id']}/financials",
                      params={"reprt_code": "11012"}).json()
    line = next(r for r in rows if r["account_nm"] == "매출액")

    assert line["thstrm_amount"] == 50, "당기가 3개월 금액입니다"
    assert line["frmtrm_amount"] == 40, "전기가 3개월 금액이라 비교가 어긋납니다"
    assert line["bfefrmtrm_amount"] is None, "중간보고서에는 전전기가 없습니다"


def test_explicit_year_still_collects_a_single_report(client, periodic, monkeypatch):
    asked = []
    monkeypatch.setattr(dart_client, "fetch_financials",
                        lambda c, y, fs_div="CFS", reprt_code=None:
                        (asked.append((y, reprt_code)) or
                         [_annual_row("BS", "자산총계", 1, "1", "1", "1")]))

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00141307", "audit_year": 2026}).json()
    r = client.post(f"{PREFIX}/companies/{created['id']}/financials",
                    params={"bsns_year": 2023})
    assert r.status_code == 200, r.text
    assert {y for y, _ in asked} == {2023}


def test_financials_survive_a_failed_disclosure_list(client, monkeypatch):
    """목록 조회가 막혀도 사업보고서까지 잃어서는 안 된다."""
    monkeypatch.setattr(dart_client, "fetch_company",
                        lambda code: {"corp_name": "회사", "acc_mt": "12"})

    def boom(*a, **k):
        raise dart_client.DartError("020")

    monkeypatch.setattr(dart_client, "fetch_disclosure_list", boom)
    monkeypatch.setattr(dart_client, "fetch_financials",
                        lambda c, y, fs_div="CFS", reprt_code=None:
                        [_annual_row("BS", "자산총계", 1, "100", "90", "80")])

    created = client.post(f"{PREFIX}/companies",
                          json={"corp_code": "00000002", "audit_year": 2026}).json()
    r = client.post(f"{PREFIX}/companies/{created['id']}/financials")

    assert r.status_code == 200, r.text
    assert r.json()["bsns_year"] == 2025


def test_the_annual_and_the_latest_interim_documents_are_both_fetched(client, monkeypatch):
    """사업보고서 주석은 완전하지만 기말에 멈춰 있고, 중간보고서는 그 반대다."""
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [
        _annual("2", "반기보고서 (2026.06)", "20260814"),
        _annual("1", "사업보고서 (2025.12)", "20260310"),
        _annual("3", "분기보고서 (2026.03)", "20260515"),
    ])
    from app.crawler import dart_document
    fetched = []
    monkeypatch.setattr(dart_document, "fetch_document",
                        lambda rcept_no: (fetched.append(rcept_no) or
                                          {f"{rcept_no}.xml": "<DOCUMENT/>"}))

    body = client.post(f"{PREFIX}/companies/{created['id']}/sections").json()

    assert set(fetched) == {"1", "2"}, "반기가 최신인데 분기를 받았습니다"
    assert body["rcept_no"] == "1", "요약의 대표는 사업보고서다"
    labels = {r["report_label"] for r in body["reports"]}
    assert labels == {"사업보고서", "반기보고서"}


def test_interim_sections_are_tagged_with_their_report(client, monkeypatch):
    """어느 보고서에서 온 구간인지 알아야 화면에서 탭을 가를 수 있다."""
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [
        _annual("2", "반기보고서 (2026.06)", "20260814"),
        _annual("1", "사업보고서 (2025.12)", "20260310"),
    ])
    from app.crawler import dart_document
    monkeypatch.setattr(dart_document, "fetch_document", lambda rcept_no: {
        f"{rcept_no}.xml":
            "<DOCUMENT><DOCUMENT-NAME>보고서</DOCUMENT-NAME><BODY>"
            "<SECTION-1><TITLE>III. 재무에 관한 사항</TITLE>"
            "<SECTION-2><TITLE>3. 재고자산</TITLE><P>내용</P></SECTION-2>"
            "</SECTION-1></BODY></DOCUMENT>",
    })

    client.post(f"{PREFIX}/companies/{created['id']}/sections")
    rows = client.get(f"{PREFIX}/companies/{created['id']}/sections").json()

    by_report = {r["report_label"] for r in rows}
    assert by_report == {"사업보고서", "반기보고서"}

    half = client.get(f"{PREFIX}/companies/{created['id']}/sections",
                      params={"reprt_code": "11012"}).json()
    assert half and all(r["report_label"] == "반기보고서" for r in half)


def test_recollecting_sections_does_not_duplicate_either_report(client, monkeypatch):
    created = _register(client, monkeypatch)
    monkeypatch.setattr(dart_client, "fetch_disclosure_list", lambda *a, **k: [
        _annual("2", "반기보고서 (2026.06)", "20260814"),
        _annual("1", "사업보고서 (2025.12)", "20260310"),
    ])
    from app.crawler import dart_document
    monkeypatch.setattr(dart_document, "fetch_document", lambda rcept_no: {
        f"{rcept_no}.xml":
            "<DOCUMENT><BODY><SECTION-1><TITLE>재고자산</TITLE>"
            "<P>내용</P></SECTION-1></BODY></DOCUMENT>",
    })

    first = client.post(f"{PREFIX}/companies/{created['id']}/sections").json()
    again = client.post(f"{PREFIX}/companies/{created['id']}/sections").json()

    assert first["total_sections"] == again["total_sections"]
    rows = client.get(f"{PREFIX}/companies/{created['id']}/sections").json()
    assert len(rows) == again["total_sections"]
