"""
ESMA (European Securities and Markets Authority) 크롤러
- European Common Enforcement Priorities (ECEP) PDF 수집
- https://www.esma.europa.eu/databases-library/esma-library 검색 결과 파싱
- 접근 제한 시 사전 등록된 연도별 ECEP PDF 목록 사용
"""
import re
import time
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.esma.europa.eu"
LIBRARY_URL = (
    "https://www.esma.europa.eu/databases-library/esma-library"
    "?search_api_fulltext=European+Common+Enforcement+Priorities"
    "&f%5B0%5D=basic_:53"
)

DOWNLOAD_DIR = Path("downloads/esma")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

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

# 사전 등록된 ECEP 연도별 PDF 목록 (크롤링 실패 시 fallback)
SEED_REPORTS = [
    {
        "report_id": "ecep-2025",
        "title": "European Common Enforcement Priorities for 2025 Corporate Reports",
        "pub_date": "2025-10-01",
        "year": 2025,
        "url": "https://www.esma.europa.eu/press-news/esma-news/esma-announces-2025-european-common-enforcement-priorities-and-results-fact",
        "pdf_url": "https://www.esma.europa.eu/sites/default/files/2025-10/ESMA32-2064178921-9254_Public_Statement_-_2025_European_Common_Enforcement_Priorities.pdf",
        "category": "ECEP",
    },
    {
        "report_id": "ecep-2024",
        "title": "European Common Enforcement Priorities for 2024 Annual Reports",
        "pub_date": "2024-10-28",
        "year": 2024,
        "url": "https://www.esma.europa.eu/press-news/esma-news/esma-announces-2024-european-common-enforcement-priorities-corporate-reporting",
        "pdf_url": "https://www.esma.europa.eu/sites/default/files/2024-10/ESMA32-193237008-8369_2024_ECEP_Statement.pdf",
        "category": "ECEP",
    },
    {
        "report_id": "ecep-2023",
        "title": "European Common Enforcement Priorities for 2023 Annual Reports",
        "pub_date": "2023-10-25",
        "year": 2023,
        "url": "https://www.esma.europa.eu/document/statement-european-common-enforcement-priorities-2023-annual-reports",
        "pdf_url": "https://www.esma.europa.eu/sites/default/files/2023-10/ESMA32-193237008-1793_2023_ECEP_Statement.pdf",
        "category": "ECEP",
    },
    {
        "report_id": "ecep-2022",
        "title": "European Common Enforcement Priorities for 2022 Annual Reports",
        "pub_date": "2022-10-28",
        "year": 2022,
        "url": "https://www.esma.europa.eu/document/esma-statement-european-common-enforcement-priorities-2022-annual-reports",
        "pdf_url": "https://www.esma.europa.eu/sites/default/files/library/esma32-63-1320_esma_statement_on_european_common_enforcement_priorities_for_2022_annual_reports.pdf",
        "category": "ECEP",
    },
    {
        "report_id": "ecep-2021",
        "title": "European Common Enforcement Priorities for 2021 Annual Financial Reports",
        "pub_date": "2021-10-29",
        "year": 2021,
        "url": "https://www.esma.europa.eu/document/public-statement-european-common-enforcement-priorities-2021",
        "pdf_url": "https://www.esma.europa.eu/sites/default/files/library/esma32-63-1186_public_statement_on_the_european_common_enforcement_priorities_2021.pdf",
        "category": "ECEP",
    },
    {
        "report_id": "ecep-2020",
        "title": "European Common Enforcement Priorities for 2020 Annual Financial Reports",
        "pub_date": "2020-10-28",
        "year": 2020,
        "url": "https://www.esma.europa.eu/document/public-statement-european-common-enforcement-priorities-2020",
        "pdf_url": "https://www.esma.europa.eu/sites/default/files/library/esma32-63-1041_public_statement_on_the_european_common_enforcement_priorities_2020.pdf",
        "category": "ECEP",
    },
    {
        "report_id": "ecep-2019",
        "title": "European Common Enforcement Priorities for 2019 Annual Financial Reports",
        "pub_date": "2019-10-29",
        "year": 2019,
        "url": "https://www.esma.europa.eu/document/public-statement-european-common-enforcement-priorities-2019",
        "pdf_url": "https://www.esma.europa.eu/sites/default/files/library/esma32-63-791_esma_european_common_enforcement_priorities_2019.pdf",
        "category": "ECEP",
    },
]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.trust_env = False
    return s


def fetch_report_list(max_items: int = 20) -> list[dict]:
    """ESMA 라이브러리에서 ECEP 문서 목록 수집.
    크롤링 실패 시 seed 목록 반환.
    """
    session = _session()

    try:
        resp = session.get(LIBRARY_URL, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"ESMA 라이브러리 접근 실패 ({e}) → seed 목록 사용")
        return SEED_REPORTS[:max_items]

    soup = BeautifulSoup(resp.text, "lxml")
    reports = _parse_library_page(soup)

    if reports:
        logger.info(f"ESMA 라이브러리 파싱 성공: {len(reports)}개 발견")
        # seed 목록과 합쳐서 중복 제거
        existing_ids = {r["report_id"] for r in reports}
        for seed in SEED_REPORTS:
            if seed["report_id"] not in existing_ids:
                reports.append(seed)
        return reports[:max_items]

    logger.info("ESMA 라이브러리 파싱 결과 없음 → seed 목록 사용")
    return SEED_REPORTS[:max_items]


def _parse_library_page(soup: BeautifulSoup) -> list[dict]:
    """ESMA 라이브러리 검색결과 페이지 파싱"""
    reports = []

    # ESMA 라이브러리는 .views-row 또는 article 태그 사용
    items = (
        soup.select(".views-row")
        or soup.select("article.esma-node")
        or soup.select(".search-result-item")
        or soup.select("article")
    )

    for item in items:
        title_el = item.select_one("h3 a, h2 a, .title a, a.esma-link")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not title or "enforcement priorities" not in title.lower():
            continue

        href = title_el.get("href", "")
        page_url = href if href.startswith("http") else BASE_URL + href

        # PDF 링크 탐색
        pdf_url = ""
        for a in item.select("a[href$='.pdf'], a[href*='/files/']"):
            href_pdf = a.get("href", "")
            if ".pdf" in href_pdf.lower():
                pdf_url = href_pdf if href_pdf.startswith("http") else BASE_URL + href_pdf
                break

        # 날짜 / 연도
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

        report_id = f"ecep-{year}" if year else _make_slug(page_url or title)

        reports.append({
            "report_id": report_id,
            "title": title,
            "pub_date": pub_date,
            "year": year,
            "url": page_url,
            "pdf_url": pdf_url,
            "category": "ECEP",
        })

    return reports


def _make_slug(text: str) -> str:
    m = re.search(r"/([^/]+?)(?:\.pdf)?$", text.rstrip("/"))
    slug = m.group(1) if m else text.lower()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug)
    return slug[:80].strip("-")


def download_pdf(url: str, report_id: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """PDF 다운로드 후 로컬 경로 반환"""
    if session is None:
        session = _session()

    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", report_id)
    save_path = DOWNLOAD_DIR / f"{safe_id}.pdf"

    if save_path.exists():
        logger.info(f"이미 다운로드됨: {save_path}")
        return str(save_path)

    try:
        resp = session.get(url, timeout=30, stream=True)
        resp.raise_for_status()

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"PDF 다운로드 완료: {save_path}")
        return str(save_path)

    except requests.RequestException as e:
        logger.error(f"PDF 다운로드 실패 ({url}): {e}")
        return None
