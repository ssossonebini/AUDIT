"""
SEC (Securities and Exchange Commission) 연설문 크롤러
- https://www.sec.gov/newsroom/speeches-statements 에서
  회계·감사 관련 연설문(AICPA 컨퍼런스 등) 수집
- PDF 없음 → HTML 본문 텍스트 직접 추출
"""
import re
import time
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sec.gov"
LIST_URL = "https://www.sec.gov/newsroom/speeches-statements"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# 회계·감사 관련 연설문 필터 키워드
RELEVANT_KEYWORDS = [
    "aicpa", "accounting", "auditing", "audit", "financial reporting",
    "chief accountant", "oca", "pcaob", "fasb", "gaap",
    "internal control", "auditor independence", "audit quality",
]

# 사전 등록된 핵심 연설문 (크롤링 실패 시 fallback)
SEED_SPEECHES = [
    {
        "speech_id": "hohl-statement-aicpa-conference-2025",
        "title": "Statement in Connection with the 2025 AICPA Conference on Current SEC and PCAOB Developments",
        "pub_date": "2025-12-08",
        "year": 2025,
        "url": "https://www.sec.gov/newsroom/speeches-statements/hohl-statement-aicpa-conference-121925",
        "speaker": "Kurt Hohl",
        "category": "AICPA Conference",
    },
    {
        "speech_id": "munter-remarks-aicpa-cima-conference-2024",
        "title": "Remarks before the 2024 AICPA & CIMA Conference on Current SEC and PCAOB Developments: Accounting Matters",
        "pub_date": "2024-12-09",
        "year": 2024,
        "url": "https://www.sec.gov/newsroom/speeches-statements/munter-remarks-aicpa-cima-conference-120924",
        "speaker": "Paul Munter",
        "category": "AICPA Conference",
    },
    {
        "speech_id": "munter-statement-investor-protection-2024",
        "title": "An Investor Protection Call for a Commitment to Professional Skepticism and Audit Quality",
        "pub_date": "2024-02-05",
        "year": 2024,
        "url": "https://www.sec.gov/newsroom/speeches-statements/munter-statement-investor-protection-020524",
        "speaker": "Paul Munter",
        "category": "Staff Statement",
    },
    {
        "speech_id": "munter-statement-lead-auditors-2023",
        "title": "Responsibilities of Lead Auditors to Conduct High-Quality Audits When Involving Other Auditors",
        "pub_date": "2023-03-17",
        "year": 2023,
        "url": "https://www.sec.gov/newsroom/speeches-statements/munter-statement-responsibilities-lead-auditors-031723",
        "speaker": "Paul Munter",
        "category": "Staff Statement",
    },
    {
        "speech_id": "munter-auditor-independence-2022",
        "title": "The Critical Importance of the General Standard of Auditor Independence and an Ethical Culture for the Accounting Profession",
        "pub_date": "2022-06-08",
        "year": 2022,
        "url": "https://www.sec.gov/newsroom/speeches-statements/munter-20220608",
        "speaker": "Paul Munter",
        "category": "Staff Statement",
    },
    {
        "speech_id": "munter-oca-focus-2021",
        "title": "Statement on OCA's Continued Focus on High Quality Financial Reporting in a Complex Environment",
        "pub_date": "2021-12-06",
        "year": 2021,
        "url": "https://www.sec.gov/newsroom/speeches-statements/munter-oca-2021-12-06",
        "speaker": "Paul Munter",
        "category": "AICPA Conference",
    },
    {
        "speech_id": "joseph-remarks-aicpa-2020",
        "title": "Remarks before the 2020 AICPA Conference on Current SEC and PCAOB Developments",
        "pub_date": "2020-12-07",
        "year": 2020,
        "url": "https://www.sec.gov/newsroom/speeches-statements/joseph-remarks-aicpa-2020",
        "speaker": "Jeffery Joseph",
        "category": "AICPA Conference",
    },
    {
        "speech_id": "teotia-speech-aicpa-2019",
        "title": "Remarks before the 2019 AICPA Conference on Current SEC and PCAOB Developments",
        "pub_date": "2019-12-09",
        "year": 2019,
        "url": "https://www.sec.gov/newsroom/speeches-statements/teotia-speech-2019-aicpa-conference",
        "speaker": "Sagar Teotia",
        "category": "AICPA Conference",
    },
    {
        "speech_id": "speech-bricker-aicpa-2018",
        "title": "Statement in Connection with the 2018 AICPA Conference on Current SEC and PCAOB Developments",
        "pub_date": "2018-12-10",
        "year": 2018,
        "url": "https://www.sec.gov/newsroom/speeches-statements/speech-bricker-121018-1",
        "speaker": "Wesley Bricker",
        "category": "AICPA Conference",
    },
]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.trust_env = False
    return s


def fetch_speech_list(max_items: int = 30) -> list[dict]:
    """연설문 목록 수집.
    SEC 목록 페이지 파싱 성공 시 동적 목록, 실패 시 seed 목록 반환.
    """
    session = _session()

    try:
        resp = session.get(LIST_URL, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"SEC 목록 페이지 접근 실패 ({e}) → seed 목록 사용")
        return SEED_SPEECHES[:max_items]

    soup = BeautifulSoup(resp.text, "lxml")
    speeches = _parse_list_page(soup)

    if speeches:
        logger.info(f"SEC 목록 파싱 성공: {len(speeches)}개 발견")
        return speeches[:max_items]

    logger.info("SEC 목록 파싱 결과 없음 → seed 목록 사용")
    return SEED_SPEECHES[:max_items]


def _parse_list_page(soup: BeautifulSoup) -> list[dict]:
    """speeches-statements 목록 페이지 파싱"""
    speeches = []

    # 다양한 listing 구조 시도
    items = (
        soup.select(".views-row")
        or soup.select(".view-content > div")
        or soup.select("article")
        or soup.select(".listing-item")
    )

    for item in items:
        title_el = item.select_one("h3 a, h2 a, .title a, a")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        # 회계·감사 관련 여부 필터
        title_lower = title.lower()
        if not any(kw in title_lower for kw in RELEVANT_KEYWORDS):
            continue

        href = title_el.get("href", "")
        url = href if href.startswith("http") else BASE_URL + href

        # 날짜
        date_el = item.select_one("time, .date, [class*='date'], span.field-content")
        pub_date = ""
        year = None
        if date_el:
            raw = date_el.get("datetime") or date_el.get_text(strip=True)
            m = re.search(r"(20\d{2})", raw)
            if m:
                year = int(m.group(1))
            pub_date = raw

        if not year:
            m = re.search(r"(20\d{2})", title)
            if m:
                year = int(m.group(1))

        # 발표자
        speaker_el = item.select_one(".speaker, .author, [class*='speaker'], [class*='author']")
        speaker = speaker_el.get_text(strip=True) if speaker_el else ""

        # 카테고리 판별
        category = _classify_category(title)

        speech_id = _make_slug(url or title)

        speeches.append({
            "speech_id": speech_id,
            "title": title,
            "pub_date": pub_date,
            "year": year,
            "url": url,
            "speaker": speaker,
            "category": category,
        })

    return speeches


def _classify_category(title: str) -> str:
    """제목에서 카테고리 분류"""
    t = title.lower()
    if "aicpa" in t:
        return "AICPA Conference"
    if "statement" in t:
        return "Staff Statement"
    if "remark" in t or "speech" in t:
        return "Remarks"
    return "Staff Publication"


def _make_slug(text: str) -> str:
    m = re.search(r"/([^/]+?)(?:\.html?)?$", text.rstrip("/"))
    slug = m.group(1) if m else text.lower()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug)
    return slug[:80].strip("-")


def fetch_speech_text(url: str, session: Optional[requests.Session] = None) -> str:
    """연설문 HTML 페이지에서 본문 텍스트 추출"""
    if session is None:
        session = _session()

    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"연설문 페이지 요청 실패 ({url}): {e}")
        return ""

    soup = BeautifulSoup(resp.text, "lxml")

    # 불필요한 요소 제거
    for tag in soup.select("nav, header, footer, script, style, .menu, .sidebar, .breadcrumb"):
        tag.decompose()

    # 본문 영역 선택 (SEC 페이지 구조에 맞게)
    content = (
        soup.select_one("article .article-content")
        or soup.select_one(".article-content")
        or soup.select_one("article")
        or soup.select_one("main")
        or soup.select_one(".content")
        or soup.select_one("#content")
        or soup.body
    )

    if not content:
        return ""

    # 텍스트 추출 및 정제
    text = content.get_text(separator="\n", strip=True)
    # 과도한 빈 줄 제거
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
