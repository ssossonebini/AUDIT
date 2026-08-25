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
