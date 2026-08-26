"""Google News RSS 파싱 검증.

이 컨테이너에서는 news.google.com 이 차단돼 실제 응답으로 확인할 수 없어,
RSS 2.0 형태를 그대로 본뜬 픽스처로 파서를 고정한다.
"""

from app.crawler import news_scraper as ns

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>"삼성전자" - Google 뉴스</title>
  <item>
    <title>삼성전자, 4분기 영업이익 9조원 - 한국경제</title>
    <link>https://news.google.com/rss/articles/CBMiAAA</link>
    <guid isPermaLink="false">CBMiAAA</guid>
    <pubDate>Mon, 25 Aug 2026 08:30:00 GMT</pubDate>
    <source url="https://www.hankyung.com">한국경제</source>
  </item>
  <item>
    <title>삼성전자 목표주가 상향 - 머니투데이</title>
    <link>https://news.google.com/rss/articles/CBMiBBB</link>
    <pubDate>Sun, 24 Aug 2026 01:00:00 GMT</pubDate>
    <source url="https://news.mt.co.kr">머니투데이</source>
  </item>
  <item>
    <title>삼성전자 협력사 소송 제기 - 매일경제</title>
    <link>https://news.google.com/rss/articles/CBMiCCC</link>
    <pubDate>Tue, 03 Mar 2020 09:00:00 GMT</pubDate>
    <source url="https://www.mk.co.kr">매일경제</source>
  </item>
  <item>
    <title>날짜 없는 기사</title>
    <link>https://news.google.com/rss/articles/CBMiDDD</link>
    <source url="https://example.com">예시신문</source>
  </item>
</channel>
</rss>
"""


# ── 파싱 ───────────────────────────────────────────────────────────

def test_parse_rss_reads_every_item():
    items = ns.parse_rss(RSS.encode("utf-8"))
    assert len(items) == 4


def test_source_suffix_is_stripped_from_the_title():
    """Google 은 제목 끝에 ' - 언론사' 를 붙인다."""
    first = ns.parse_rss(RSS.encode("utf-8"))[0]
    assert first["title"] == "삼성전자, 4분기 영업이익 9조원"
    assert first["source"] == "한국경제"


def test_suffix_that_is_not_the_source_name_is_kept():
    rss = RSS.replace("영업이익 9조원 - 한국경제", "영업이익 - 사상 최대")
    first = ns.parse_rss(rss.encode("utf-8"))[0]
    assert first["title"].endswith("사상 최대"), "본문의 하이픈을 잘라내면 안 된다"


def test_pub_date_becomes_an_iso_date():
    assert ns.parse_pub_date("Mon, 25 Aug 2026 08:30:00 GMT") == "2026-08-25"


def test_pub_date_survives_a_malformed_value():
    assert ns.parse_pub_date("언젠가") is None
    assert ns.parse_pub_date(None) is None


def test_broken_xml_yields_nothing_rather_than_raising():
    assert ns.parse_rss(b"<rss><channel><item>") == []


# ── 걸러내기 ───────────────────────────────────────────────────────

def test_stock_chatter_is_treated_as_noise():
    assert ns.is_noise("삼성전자 목표주가 상향") is True
    assert ns.is_noise("코스피 마감 시황") is True


def test_substantive_headlines_are_not_noise():
    assert ns.is_noise("삼성전자, 4분기 영업이익 9조원") is False
    assert ns.is_noise("삼성전자 협력사 소송 제기") is False


def test_window_keeps_undated_items():
    """날짜를 모른다고 버리면 최근 기사를 놓칠 수 있다."""
    assert ns.within(None, "2025-01-01", "2026-08-26") is True


def test_window_excludes_older_articles():
    assert ns.within("2020-03-03", "2025-01-01", "2026-08-26") is False
    assert ns.within("2026-08-25", "2025-01-01", "2026-08-26") is True


# ── 수집 ───────────────────────────────────────────────────────────

def test_collect_filters_noise_and_out_of_window(monkeypatch):
    monkeypatch.setattr(ns, "fetch_news",
                        lambda q, session=None: ns.parse_rss(RSS.encode("utf-8")))

    got = ns.collect("삼성전자", "2025-01-01", "2026-08-26", angles=("",))
    titles = [g["title"] for g in got]

    assert "삼성전자, 4분기 영업이익 9조원" in titles
    assert "날짜 없는 기사" in titles              # 날짜 불명은 남긴다
    assert not any("목표주가" in t for t in titles)  # 잡음
    assert not any("소송 제기" in t for t in titles)  # 2020년 — 창 밖


def test_collect_deduplicates_across_query_angles(monkeypatch):
    """갈래별 질의가 같은 기사를 물어온다. 한 번만 저장해야 한다."""
    calls = []

    def fake(query, session=None):
        calls.append(query)
        return ns.parse_rss(RSS.encode("utf-8"))

    monkeypatch.setattr(ns, "fetch_news", fake)
    got = ns.collect("삼성전자", "2025-01-01", "2026-08-26",
                     angles=("", "실적", "소송"))

    assert len(calls) == 3, "갈래마다 질의해야 한다"
    assert len(got) == len({g["title"] for g in got}), "중복이 저장됐습니다"


def test_collect_sorts_newest_first(monkeypatch):
    monkeypatch.setattr(ns, "fetch_news",
                        lambda q, session=None: ns.parse_rss(RSS.encode("utf-8")))
    got = ns.collect("삼성전자", "2025-01-01", "2026-08-26", angles=("",))
    dates = [g["published_at"] for g in got if g["published_at"]]
    assert dates == sorted(dates, reverse=True)


def test_query_quotes_the_company_name():
    """따옴표가 없으면 이름이 부분일치해 엉뚱한 기사가 섞인다."""
    assert ns.build_query("삼성전자") == '"삼성전자"'
    assert ns.build_query("삼성전자", "실적") == '"삼성전자" 실적'


# ── 태깅 ───────────────────────────────────────────────────────────

def test_classify_rejects_a_tag_that_is_not_in_the_taxonomy(monkeypatch):
    """모델이 없는 분류를 지어내면 미분류로 떨어뜨린다."""
    class _Msg:
        content = [type("C", (), {"text": '{"tag": "기타", "reason": "음"}'})()]

    class _Client:
        def __init__(self, **kw): pass
        messages = type("M", (), {"create": staticmethod(lambda **kw: _Msg())})()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _Client)

    assert ns.classify("제목", "삼성전자", "key")["tag"] is None


def test_classify_returns_untagged_when_the_call_fails(monkeypatch):
    import anthropic

    def boom(**kw):
        raise RuntimeError("네트워크 오류")

    monkeypatch.setattr(anthropic, "Anthropic", boom)
    result = ns.classify("제목", "삼성전자", "key")

    assert result == {"tag": None, "reason": ""}


# ── 놓쳤던 기사 ────────────────────────────────────────────────────

SANCTION = "금융위, '회계처리 위반' 영풍에 과징금 204억…고려아연 84억"


def test_accounting_sanction_headline_survives_the_noise_filter():
    """회계처리기준 위반 과징금은 감사와 가장 직접 맞닿는 사건이다."""
    assert ns.is_noise(SANCTION) is False


def test_plant_shutdown_is_not_mistaken_for_stock_chatter():
    """'공장중단' 에 '장중' 이 들어 있어 조업정지 기사가 잘려나갔다."""
    assert ns.is_noise("영풍 석포제련소 공장중단 명령") is False
    assert ns.is_noise("영풍 조업정지 처분 취소 소송") is False


def test_genuine_stock_chatter_is_still_dropped():
    for title in ("영풍 목표주가 상향", "코스피 마감 시황", "오늘의 테마주"):
        assert ns.is_noise(title) is True, title


def test_query_angles_use_or_not_juxtaposition():
    """띄어쓴 낱말은 Google 에서 AND 로 묶인다.

    '소송 제재' 는 둘을 모두 담은 기사만 걸러, 과징금 기사를 놓쳤다.
    """
    for angle in ns.QUERY_ANGLES:
        if " " in angle:
            assert " OR " in angle, f"'{angle}' 이 AND 로 동작합니다"


def test_an_angle_covers_accounting_enforcement():
    """회계 제재를 겨냥한 갈래가 있어야 일반 질의의 100건 상한에 안 밀린다."""
    joined = " ".join(ns.QUERY_ANGLES)
    for word in ("회계", "감리", "과징금", "증선위"):
        assert word in joined, f"{word} 를 겨냥한 갈래가 없습니다"


# ── 회사명 정규화 ──────────────────────────────────────────────────
#
# DART 는 '(주)영풍' 을 주지만 기사 제목은 '영풍' 이라고 쓴다. 따옴표로 묶은
# 구문 검색에서는 이 차이가 그대로 불일치가 되어 과징금 기사가 통째로 빠졌다.

def test_legal_form_is_stripped_from_the_search_name():
    for raw in ("(주)영풍", "㈜영풍", "주식회사 영풍", "영풍"):
        assert ns.search_name(raw) == "영풍", raw


def test_trailing_legal_form_is_stripped_too():
    assert ns.search_name("삼성전자주식회사") == "삼성전자"
    assert ns.search_name("에스케이하이닉스(주)") == "에스케이하이닉스"
    assert ns.search_name("현대자동차 주식회사") == "현대자동차"


def test_english_legal_form_is_stripped():
    assert ns.search_name("SK Inc.") == "SK"
    assert ns.search_name("Hyundai Motor Co., Ltd.") == "Hyundai Motor"


def test_a_name_that_is_not_a_legal_form_is_left_alone():
    for raw in ("한국가스공사", "영풍제지", "주성엔지니어링"):
        assert ns.search_name(raw) == raw, raw


def test_a_name_that_would_vanish_keeps_its_original_form():
    """떼어내고 한 글자만 남으면 검색어 노릇을 못 한다."""
    assert ns.search_name("(주)티") == "(주)티"


def test_the_query_uses_the_normalized_name():
    assert ns.build_query("(주)영풍") == '"영풍"'
    assert ns.build_query("(주)영풍", "회계 OR 과징금") == '"영풍" 회계 OR 과징금'
