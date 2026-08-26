"""DART 응답 파싱 검증.

응답 형태의 함정이 여기 몰려 있다 (CLAUDE.md 참조).
- 분기·반기에는 bfefrmtrm_* 키가 아예 없다 → KeyError 유발
- 분기 손익계산서의 전기는 frmtrm_amount 가 아니라 frmtrm_q_amount
- 분기 손익계산서의 thstrm_amount 는 3개월치, 누적은 thstrm_add_amount
"""

from app.crawler import dart_client as dc


# ── 금액 파싱 ──────────────────────────────────────────────────────

def test_parse_amount_strips_thousands_separators():
    assert dc.parse_amount("9,999,999,999") == 9999999999


def test_parse_amount_handles_negatives():
    assert dc.parse_amount("-1,234,567") == -1234567


def test_parse_amount_treats_blank_and_dash_as_missing():
    for blank in ("", "  ", "-", None):
        assert dc.parse_amount(blank) is None


def test_parse_amount_survives_unexpected_text():
    assert dc.parse_amount("해당사항없음") is None


# ── 전기 금액: 재무제표 구분에 따라 필드가 다르다 ──────────────────

def test_prior_amount_uses_frmtrm_for_annual_reports():
    row = {"frmtrm_amount": "1,000", "frmtrm_q_amount": ""}
    assert dc.prior_amount(row) == 1000


def test_prior_amount_falls_back_to_quarterly_field():
    """분기 IS/CIS 는 frmtrm_amount 가 비고 frmtrm_q_amount 에 값이 온다."""
    row = {"frmtrm_amount": "", "frmtrm_q_amount": "2,500"}
    assert dc.prior_amount(row) == 2500


def test_prior_amount_when_quarterly_key_is_absent():
    assert dc.prior_amount({"frmtrm_amount": "700"}) == 700


def test_prior_amount_returns_none_when_both_missing():
    assert dc.prior_amount({}) is None


# ── 당기 금액: 분기는 3개월치라 누적을 우선한다 ────────────────────

def test_current_amount_prefers_cumulative_in_quarterly_reports():
    row = {"thstrm_amount": "300", "thstrm_add_amount": "900"}   # 3개월 vs 누적
    assert dc.current_amount(row) == 900


def test_current_amount_uses_period_figure_when_cumulative_is_blank():
    """사업보고서는 thstrm_add_amount 키가 있어도 값이 비어 있다."""
    row = {"thstrm_amount": "5,000", "thstrm_add_amount": ""}
    assert dc.current_amount(row) == 5000


def test_current_amount_can_ask_for_the_period_figure():
    row = {"thstrm_amount": "300", "thstrm_add_amount": "900"}
    assert dc.current_amount(row, cumulative=False) == 300


# ── 전전기: 사업보고서에만 존재하는 키 ─────────────────────────────

def test_missing_bfefrmtrm_key_does_not_raise():
    """분기 응답에는 이 키가 없다. [] 로 접근하면 KeyError 가 난다."""
    quarterly_row = {"thstrm_amount": "100", "frmtrm_q_amount": "90"}
    assert dc.parse_amount(quarterly_row.get("bfefrmtrm_amount")) is None


def test_annual_row_yields_three_years():
    row = {
        "sj_div": "BS",
        "thstrm_amount": "3,000",
        "frmtrm_amount": "2,000",
        "bfefrmtrm_amount": "1,000",
    }
    assert dc.current_amount(row) == 3000
    assert dc.prior_amount(row) == 2000
    assert dc.parse_amount(row["bfefrmtrm_amount"]) == 1000


# ── 오류 코드 ──────────────────────────────────────────────────────

def test_dart_error_carries_a_readable_message():
    err = dc.DartError("020")
    assert err.status == "020"
    assert "요청 제한" in str(err)


def test_dart_error_falls_back_for_unknown_status():
    assert "알 수 없는 오류" in str(dc.DartError("999"))


# ── 정기보고서 이름 읽기 ────────────────────────────────────────────
#
# 「분기보고서」는 1분기와 3분기가 같은 이름을 쓴다. 괄호 안의 기간 종료월로만
# 갈린다. 이 목록이 곧 그 회사의 공시 주기이므로, 분기를 내는 회사인지 따로
# 판정할 필요가 없다.

def test_annual_report_name_is_read():
    got = dc.parse_periodic_report("사업보고서 (2025.12)")
    assert got["reprt_code"] == dc.REPRT_ANNUAL
    assert got["bsns_year"] == 2025


def test_half_year_report_name_is_read():
    got = dc.parse_periodic_report("반기보고서 (2026.06)")
    assert got["reprt_code"] == dc.REPRT_HALF
    assert got["bsns_year"] == 2026


def test_the_two_quarters_are_told_apart_by_their_closing_month():
    q1 = dc.parse_periodic_report("분기보고서 (2026.03)")
    q3 = dc.parse_periodic_report("분기보고서 (2026.09)")
    assert q1["reprt_code"] == dc.REPRT_Q1
    assert q3["reprt_code"] == dc.REPRT_Q3


def test_a_corrected_filing_is_still_recognised():
    got = dc.parse_periodic_report("[기재정정]사업보고서 (2025.12)")
    assert got["reprt_code"] == dc.REPRT_ANNUAL


def test_a_march_year_end_shifts_every_quarter():
    """3월 결산의 1분기는 6월에 끝난다. 달만 보고 판정하면 어긋난다."""
    q1 = dc.parse_periodic_report("분기보고서 (2026.06)", fiscal_month=3)
    q3 = dc.parse_periodic_report("분기보고서 (2025.12)", fiscal_month=3)
    half = dc.parse_periodic_report("반기보고서 (2026.09)", fiscal_month=3)

    assert q1["reprt_code"] == dc.REPRT_Q1
    assert q3["reprt_code"] == dc.REPRT_Q3
    assert half["reprt_code"] == dc.REPRT_HALF


def test_a_year_that_straddles_two_calendar_years_uses_the_opening_year():
    """3월 결산의 「사업보고서 (2026.03)」은 사업연도 2025다."""
    got = dc.parse_periodic_report("사업보고서 (2026.03)", fiscal_month=3)
    assert got["bsns_year"] == 2025


def test_non_periodic_filings_are_not_mistaken_for_reports():
    for name in ("감사보고서제출", "주요사항보고서(자기주식취득결정)",
                 "회계처리기준 위반에 따른 임원의 해임권고 조치"):
        assert dc.parse_periodic_report(name) is None, name


# ── 분기 금액 필드 ──────────────────────────────────────────────────

def test_prior_period_uses_the_same_basis_as_the_current_one():
    """당기를 누적으로 읽고 전기를 3개월로 읽으면 전년 동기 대비가 어긋난다."""
    row = {"thstrm_amount": "10", "thstrm_add_amount": "50",
           "frmtrm_q_amount": "20", "frmtrm_add_amount": "40"}

    assert dc.current_amount(row) == 50
    assert dc.prior_amount(row) == 40, "전기가 3개월 금액입니다"


def test_the_annual_report_is_unaffected_by_the_cumulative_rule():
    row = {"thstrm_amount": "100", "frmtrm_amount": "90", "bfefrmtrm_amount": "80"}
    assert dc.current_amount(row) == 100
    assert dc.prior_amount(row) == 90
