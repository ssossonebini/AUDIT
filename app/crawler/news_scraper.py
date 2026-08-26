"""회사 뉴스 수집 — Google News RSS.

네이버 검색 API는 NCP 가입이 필요해 후순위로 두고, 키가 필요 없는 Google News
RSS 를 쓴다. 반환은 RSS 2.0 이고 제목·링크·발행일·언론사가 들어온다.

한계 두 가지를 알고 쓴다.
- 한 질의당 대략 100건이 상한이라, 질의를 몇 갈래로 나눠 재현율을 올린다.
- link 는 news.google.com 리디렉션 주소다. 클릭하면 원문으로 가지만 원문
  도메인이 바로 드러나지 않아, 언론사명은 <source> 태그에서 따로 읽는다.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

RSS_URL = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
}

# 회사명만으로 검색하면 주가·분쟁 기사에 묻힌다. 감사에서 볼 만한 갈래를 함께 던진다.
#
# **OR 를 명시해야 한다.** 띄어쓴 낱말은 Google 에서 AND 로 묶여, "소송 제재" 는
# 둘을 모두 담은 기사만 걸린다. 실제로 영풍의 금융위 과징금 기사(2026-07-15)가
# 이 때문에 빠졌다 — 제목에 과징금은 있어도 제재는 없었다.
#
# 회계 갈래를 따로 둔 것은 회계처리기준 위반·감리 조치가 감사와 가장 직접
# 맞닿는 사건이기 때문이다. 일반 질의는 분쟁 기사에 밀려 상한에 걸린다.
QUERY_ANGLES = (
    "",
    "회계 OR 감리 OR 과징금 OR 증선위 OR 금융감독원 OR 재무제표",
    "제재 OR 조사 OR 소송 OR 분쟁 OR 처분",
    "실적 OR 영업이익 OR 적자 OR 손실",
    "인수 OR 합병 OR 매각 OR 분할 OR 지분",
    "증자 OR 차입 OR 자금조달 OR 신용등급",
)

# 제목만으로 걸러낼 수 있는 잡음 — AI 호출 전에 쳐낸다.
#
# 부분일치로 보므로 짧고 흔한 말은 넣지 않는다. "장중" 은 "공장중단" 을 잘라내
# 조업정지 기사를 통째로 버렸다. 놓치는 비용(과징금 기사 유실)이 통과시키는
# 비용($0.001)보다 훨씬 크므로, 애매하면 통과시킨다.
NOISE_KEYWORDS = (
    "목표주가", "투자의견", "매수 추천", "매도 추천", "적정주가",
    "상한가", "하한가", "코스피 마감", "코스닥 마감", "증시 브리핑",
    "테마주", "주가 전망", "장중 한때", "오늘의 운세", "부고",
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def build_query(corp_name: str, angle: str = "") -> str:
    """회사명을 따옴표로 묶어 부분일치를 막고, 갈래 키워드를 덧붙인다."""
    q = f'"{corp_name}"'
    return f"{q} {angle}".strip()


def fetch_news(query: str, session: Optional[requests.Session] = None) -> list[dict]:
    """한 질의의 RSS 를 받아 항목 목록으로 돌려준다."""
    if session is None:
        session = _session()

    url = RSS_URL.format(query=quote(query))
    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"뉴스 조회 실패 ({query}): {e}")
        return []

    return parse_rss(resp.content)


def parse_rss(content: bytes) -> list[dict]:
    """RSS 2.0 바이트열 → 항목 목록. 깨진 항목은 건너뛴다."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        logger.warning(f"RSS 파싱 실패: {e}")
        return []

    items = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        if not title:
            continue

        source_node = node.find("source")
        source = (source_node.text or "").strip() if source_node is not None else ""

        items.append({
            "title": strip_source_suffix(title, source),
            "url": (node.findtext("link") or "").strip(),
            "source": source,
            "published_at": parse_pub_date(node.findtext("pubDate")),
        })

    return items


def strip_source_suffix(title: str, source: str) -> str:
    """Google 은 제목 끝에 ' - 언론사' 를 붙인다. 언론사명과 일치할 때만 뗀다."""
    if source and title.endswith(f" - {source}"):
        return title[: -(len(source) + 3)].strip()
    return title


def parse_pub_date(value: Optional[str]) -> Optional[str]:
    """RFC 822 (예: 'Mon, 25 Aug 2026 08:30:00 GMT') → 'YYYY-MM-DD'."""
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.date().isoformat()


def is_noise(title: str) -> bool:
    """주가·시황 기사처럼 감사와 무관한 잡음인지 제목만으로 본다."""
    cleaned = (title or "").replace(" ", "")
    return any(kw.replace(" ", "") in cleaned for kw in NOISE_KEYWORDS)


def within(published_at: Optional[str], bgn: str, end: str) -> bool:
    """수집 창 안의 기사인지. 날짜를 모르면 남긴다 (버리는 쪽이 손해다)."""
    if not published_at:
        return True
    return bgn <= published_at <= end


def collect(
    corp_name: str,
    bgn: str,
    end: str,
    angles: tuple[str, ...] = QUERY_ANGLES,
) -> list[dict]:
    """갈래별로 질의해 모으고, 창 밖·잡음·중복을 걸러 돌려준다.

    Args:
        bgn, end: 'YYYY-MM-DD'
    """
    session = _session()
    seen_titles: set[str] = set()
    results: list[dict] = []

    for angle in angles:
        query = build_query(corp_name, angle)
        for item in fetch_news(query, session):
            key = re.sub(r"\s+", "", item["title"])
            if key in seen_titles:
                continue
            if is_noise(item["title"]):
                continue
            if not within(item["published_at"], bgn, end):
                continue

            seen_titles.add(key)
            item["query"] = query
            results.append(item)

    results.sort(key=lambda x: x["published_at"] or "", reverse=True)
    logger.info(f"뉴스 {len(results)}건 수집 ({corp_name})")
    return results


# ── 감사 어서션 태깅 ───────────────────────────────────────────────

# CLAUDE.md 의 4분류. 감사에서 무엇을 볼지와 직접 이어지도록 잡았다.
NEWS_TAGS = {
    "산업·업황":    "재고 평가, 손상징후",
    "재무·실적":    "수익인식, 계속기업",
    "사업구조 변동": "사업결합, 무형자산",
    "리스크":       "충당부채, 우발부채, 소송",
}

_CLASSIFY_PROMPT = """다음은 '{corp_name}'에 관한 뉴스 제목입니다.
외부감사인 관점에서 이 기사가 재무제표 감사에 시사점이 있는지 판단하세요.

제목: {title}

시사점이 있다면 아래 넷 중 하나로 분류하고, 없으면 tag 를 null 로 두세요.
- "산업·업황": 업황 악화·호전, 원자재, 수요 변동 → 재고 평가·손상징후
- "재무·실적": 실적, 자금조달, 유동성, 신용등급 → 수익인식·계속기업
- "사업구조 변동": 인수, 합병, 분할, 매각, 신규 진출 → 사업결합·무형자산
- "리스크": 소송, 제재, 조사, 사고, 리콜 → 충당부채·우발부채

아래 JSON 형식으로만 답하세요.
{{"tag": "산업·업황" 또는 null, "reason": "한 줄 이유"}}"""


def classify(title: str, corp_name: str, api_key: str) -> dict:
    """뉴스 한 건을 4분류 중 하나로 태깅한다. 실패하면 미분류로 남긴다."""
    import json

    import anthropic

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": _CLASSIFY_PROMPT.format(corp_name=corp_name, title=title),
            }],
        )
        text = msg.content[0].text.strip()
        match = re.search(r"\{.*\}", text, re.S)
        result = json.loads(match.group(0) if match else text)
    except Exception as e:
        logger.warning(f"뉴스 분류 실패: {e}")
        return {"tag": None, "reason": ""}

    tag = result.get("tag")
    if tag not in NEWS_TAGS:      # 모델이 없는 분류를 지어내면 버린다
        tag = None
    return {"tag": tag, "reason": (result.get("reason") or "").strip()}
