"""
PCAOB Staff Publications 크롤러
- https://pcaobus.org/resources/staff-publications 에서 게시물 목록 수집
- PDF 파일 다운로드
"""
import re
import time
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://pcaobus.org"
ASSETS_URL = "https://assets.pcaobus.org"
PUBLICATIONS_URL = "https://pcaobus.org/resources/staff-publications"

DOWNLOAD_DIR = Path("downloads/pcaob")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

# 사전 등록된 PCAOB 주요 게시물 (크롤링 실패 시 fallback)
SEED_PUBLICATIONS = [
    {
        "pub_id": "2025-priorities-spotlight",
        "title": "Spotlight: 2025 Inspection Priorities",
        "pub_date": "2024-12-09",
        "year": 2025,
        "url": "https://pcaobus.org/news-events/news-releases/news-release-detail/pcaob-staff-report-outlines-2025-inspection-priorities-with-focus-on-driving-improvements-in-audit-quality",
        "pdf_url": "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/2025-priorities-spotlight_v3.pdf",
        "category": "Spotlight",
    },
    {
        "pub_id": "staff-update-2024-inspection-activities",
        "title": "Spotlight: Staff Update on 2024 Inspection Activities",
        "pub_date": "2025-03-01",
        "year": 2024,
        "url": "https://pcaobus.org/resources/staff-publications",
        "pdf_url": "https://pcaobus.org/documents/staff-update-2024-inspection-activities-spotlight.pdf",
        "category": "Spotlight",
    },
    {
        "pub_id": "2024-priorities-spotlight",
        "title": "Spotlight: 2024 Inspection Priorities",
        "pub_date": "2023-12-12",
        "year": 2024,
        "url": "https://pcaobus.org/news-events/news-releases/news-release-detail/pcaob-staff-outline-2024-inspection-priorities-with-focus-on-driving-improvements-in-audit-quality",
        "pdf_url": "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/2024-inspection-priorities-spotlight.pdf",
        "category": "Spotlight",
    },
    {
        "pub_id": "illegal-acts-spotlight",
        "title": "Spotlight: Auditor Responsibilities for Detecting, Evaluating, and Making Communications About Illegal Acts",
        "pub_date": "2024-06-12",
        "year": 2024,
        "url": "https://pcaobus.org/resources/staff-publications",
        "pdf_url": "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/illegal-acts-spotlight.pdf",
        "category": "Spotlight",
    },
    {
        "pub_id": "generative-ai-outreach-spotlight",
        "title": "Spotlight: Staff Update on Outreach Activities Related to the Integration of Generative Artificial Intelligence in Audits and Financial Reporting",
        "pub_date": "2024-09-10",
        "year": 2024,
        "url": "https://pcaobus.org/resources/staff-publications",
        "pdf_url": "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/gen-ai-outreach-spotlight.pdf",
        "category": "Spotlight",
    },
    {
        "pub_id": "auditor-independence-spotlight",
        "title": "Spotlight: Inspection Observations Related to Auditor Independence",
        "pub_date": "2024-04-16",
        "year": 2024,
        "url": "https://pcaobus.org/resources/staff-publications",
        "pdf_url": "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/auditor-independence-spotlight.pdf",
        "category": "Spotlight",
    },
    {
        "pub_id": "target-team-2023-inspections-spotlight",
        "title": "Spotlight: Observations From the Target Team's 2023 Inspections",
        "pub_date": "2024-02-28",
        "year": 2023,
        "url": "https://pcaobus.org/resources/staff-publications",
        "pdf_url": "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/target-team-2023-inspections-spotlight.pdf",
        "category": "Spotlight",
    },
    {
        "pub_id": "staff-update-2023-inspection-activities",
        "title": "Spotlight: Staff Update on 2023 Inspection Activities",
        "pub_date": "2024-03-06",
        "year": 2023,
        "url": "https://pcaobus.org/resources/staff-publications",
        "pdf_url": "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/staff-update-2023-inspection-activities-spotlight.pdf",
        "category": "Spotlight",
    },
    {
        "pub_id": "2023-priorities-spotlight",
        "title": "Spotlight: 2023 Inspection Priorities",
        "pub_date": "2022-12-06",
        "year": 2023,
        "url": "https://pcaobus.org/resources/staff-publications",
        "pdf_url": "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/2023-inspection-priorities-spotlight.pdf",
        "category": "Spotlight",
    },
]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.trust_env = False
    return s


def fetch_publication_list(max_items: int = 50) -> list[dict]:
    """Staff Publications 페이지 크롤링 → 게시물 메타데이터 수집.
    HTML 파싱에 성공하면 동적 목록을 반환하고,
    실패하면 사전 등록된 seed 목록을 반환한다.
    """
    session = _session()

    try:
        resp = session.get(PUBLICATIONS_URL, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"PCAOB 페이지 접근 실패 ({e}) → seed 목록 사용")
        return SEED_PUBLICATIONS[:max_items]

    soup = BeautifulSoup(resp.text, "lxml")
    publications = _parse_publications_page(soup)

    if publications:
        logger.info(f"HTML 파싱 성공: {len(publications)}개 게시물 발견")
        return publications[:max_items]

    logger.info("HTML 파싱 결과 없음 → seed 목록 사용")
    return SEED_PUBLICATIONS[:max_items]


def _parse_publications_page(soup: BeautifulSoup) -> list[dict]:
    """PCAOB staff-publications 페이지 HTML 파싱"""
    publications = []

    # 패턴 1: 일반적인 listing 구조
    selectors = [
        ".listing-item",
        ".publication-item",
        ".resource-item",
        "article.item",
        ".content-item",
        ".results-item",
    ]
    items = []
    for sel in selectors:
        items = soup.select(sel)
        if items:
            break

    # 패턴 2: 링크 텍스트 기반 탐색 (fallback)
    if not items:
        items = _collect_link_containers(soup)

    for item in items:
        pub = _parse_item(item)
        if pub and pub.get("title") and len(pub["title"]) > 5:
            publications.append(pub)

    return publications


def _collect_link_containers(soup: BeautifulSoup) -> list:
    """링크를 포함하는 컨테이너 블록 수집 (JS 렌더 페이지 fallback)"""
    seen = set()
    containers = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        # 관련성 있는 링크만 대상
        if not text or len(text) < 15:
            continue
        if any(kw in href.lower() for kw in ["spotlight", "staff-guidance", "staff-audit", "/documents/", "staff-publication"]):
            parent = a.parent
            key = parent.get_text(strip=True)[:80]
            if key not in seen:
                seen.add(key)
                containers.append(parent)
    return containers


def _parse_item(item) -> Optional[dict]:
    """단일 publication 항목 파싱"""
    # 제목
    title_el = item.select_one("h2, h3, h4, .title, a")
    if not title_el:
        return None
    title = title_el.get_text(strip=True)
    if not title:
        return None

    # 페이지 URL
    link = item.select_one("a[href]")
    url = ""
    if link:
        href = link.get("href", "")
        url = href if href.startswith("http") else BASE_URL + href

    # PDF URL
    pdf_url = ""
    for a in item.select("a[href]"):
        href = a.get("href", "")
        if ".pdf" in href.lower():
            pdf_url = href if href.startswith("http") else BASE_URL + href
            break

    # 날짜 / 연도
    pub_date = ""
    year = None
    date_el = item.select_one("time, .date, .pub-date, [class*='date']")
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

    # 카테고리
    cat_el = item.select_one(".category, .tag, [class*='type'], [class*='category']")
    category = cat_el.get_text(strip=True) if cat_el else "Staff Publication"
    if "spotlight" in title.lower():
        category = "Spotlight"

    # pub_id: URL slug 또는 제목 slug
    pub_id = _make_slug(url or title)

    return {
        "pub_id": pub_id,
        "title": title,
        "pub_date": pub_date,
        "year": year,
        "url": url,
        "pdf_url": pdf_url,
        "category": category,
    }


def _make_slug(text: str) -> str:
    """URL 또는 제목에서 slug 생성"""
    # URL의 마지막 경로 세그먼트 사용
    m = re.search(r"/([^/]+?)(?:\.pdf)?$", text.rstrip("/"))
    if m:
        slug = m.group(1)
    else:
        slug = text.lower()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug)
    return slug[:80].strip("-")


def download_pdf(url: str, pub_id: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """PDF 다운로드 후 로컬 경로 반환"""
    if session is None:
        session = _session()

    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", pub_id)
    save_path = DOWNLOAD_DIR / f"{safe_id}.pdf"

    if save_path.exists():
        logger.info(f"이미 다운로드됨: {save_path}")
        return str(save_path)

    try:
        resp = session.get(url, timeout=30, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        content_disp = resp.headers.get("Content-Disposition", "")
        if "pdf" not in content_type.lower() and "pdf" not in content_disp.lower():
            if not url.lower().endswith(".pdf"):
                logger.warning(f"PDF 아닌 응답 (Content-Type: {content_type})")

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"PDF 다운로드 완료: {save_path}")
        return str(save_path)

    except requests.RequestException as e:
        logger.error(f"PDF 다운로드 실패 ({url}): {e}")
        return None
