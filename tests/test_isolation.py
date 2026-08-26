"""테스트가 바깥 세상에 손대지 못하게 막는 장치를 검증한다.

두 가지를 막는다.
- 실제 audit.db (conftest.py 가 AUDIT_DATABASE_URL 을 임시 파일로 돌린다)
- 실제 네트워크

둘 다 한 번씩 실제로 사고가 났던 자리다. DB 는 픽스처의 drop_all 이 수집
데이터를 지웠고, 네트워크는 대역을 빠뜨린 세 테스트가 .env 의 DART_API_KEY 로
진짜 공시 목록을 받아왔다. 키가 없는 환경에서는 통과하고 키가 있는 로컬에서만
깨져서, 원인을 찾기 전까지 로직 결함처럼 보였다.
"""

import pathlib

import pytest

from tests.conftest import NetworkAccessInTests


# ── 네트워크 ───────────────────────────────────────────────────────

def test_a_forgotten_stub_fails_loudly_instead_of_calling_dart():
    import requests

    with pytest.raises(NetworkAccessInTests):
        requests.get("https://opendart.fss.or.kr/api/list.json")


def test_a_session_also_cannot_reach_out():
    """news_scraper 는 Session 을 쓴다. requests.get 만 막으면 새어나간다."""
    import requests

    with pytest.raises(NetworkAccessInTests):
        requests.Session().get("https://news.google.com/rss/search?q=x")


def test_posting_is_blocked_too():
    import requests

    with pytest.raises(NetworkAccessInTests):
        requests.post("https://api.anthropic.com/v1/messages", json={})


def test_a_test_that_stubs_properly_is_not_blocked(monkeypatch):
    """대역을 건 테스트는 그대로 동작해야 한다 — 나중에 건 쪽이 이긴다."""
    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: "대역 응답")
    assert requests.get("https://example.com") == "대역 응답"


# ── 데이터베이스 ───────────────────────────────────────────────────

def test_the_engine_never_points_at_the_real_database():
    from app.db.database import DEFAULT_DATABASE_URL, engine

    target = pathlib.Path(str(engine.url).replace("sqlite:///", "")).name
    real = pathlib.Path(DEFAULT_DATABASE_URL.replace("sqlite:///", "")).name

    assert target != real, "테스트가 실제 audit.db 에 붙어 있습니다"
