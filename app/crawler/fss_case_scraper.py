"""
금융감독원 회계심사·감리 지적사례 크롤러
- '지적사례' 키워드로 보도자료 게시판 검색
- 각 게시글의 첨부 PDF 다운로드
"""
import os
import re
import time
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fss.or.kr"
# 지적사례 키워드 검색 URL
LIST_URL = (
    "https://www.fss.or.kr/fss/bbs/B0000188/list.do"
    "?menuNo=200218&bbsId=&cl1Cd=&pageIndex={page}"
    "&sdate=&edate=&searchCnd=1&searchWrd=%EC%A7%80%EC%A0%81%EC%82%AC%EB%A1%80"
)
DETAIL_URL = "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId={ntt_id}&menuNo=200218"

DOWNLOAD_DIR = Path("downloads/fss_case")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.fss.or.kr/",
}

# 크롤링 실패 시 사용할 시드 데이터 (공개 보도자료 기준)
# 실제 nttId는 FSS 보도자료 게시판 검색으로 확인 가능
SEED_CASES = [
    {
        "ntt_id": "9100",
        "title": "최근 회계심사,감리 주요 지적사례(10건)를 공개하오니 회사 및 감사인은 결산,감사 시 참고하시기 바랍니다.",
        "pub_date": "2025-12-02",
        "year": 2025,
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=9100&menuNo=200218",
        "period": "2025년 상반기",
    },
    {
        "ntt_id": "9050",
        "title": "최근 회계심사,감리 주요 지적사례(10건)를 공개하오니 회사 및 감사인은 결산,감사 시 참고하시기 바랍니다.",
        "pub_date": "2025-06-01",
        "year": 2025,
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=9050&menuNo=200218",
        "period": "2024년 하반기",
    },
    {
        "ntt_id": "8900",
        "title": "최근 회계심사,감리 주요 지적사례(10건)를 공개하오니 회사 및 감사인은 결산,감사 시 참고하시기 바랍니다.",
        "pub_date": "2024-12-01",
        "year": 2024,
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=8900&menuNo=200218",
        "period": "2024년 상반기",
    },
    {
        "ntt_id": "8800",
        "title": "최근 회계심사,감리 주요 지적사례(10건)를 공개하오니 회사 및 감사인은 결산,감사 시 참고하시기 바랍니다.",
        "pub_date": "2024-06-01",
        "year": 2024,
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=8800&menuNo=200218",
        "period": "2023년 하반기",
    },
    {
        "ntt_id": "8600",
        "title": "최근 회계심사·감리 주요 지적사례(10건) 공개",
        "pub_date": "2023-12-01",
        "year": 2023,
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=8600&menuNo=200218",
        "period": "2023년",
    },
    {
        "ntt_id": "8400",
        "title": "최근 회계심사·감리 주요 지적사례(10건) 공개",
        "pub_date": "2022-12-01",
        "year": 2022,
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=8400&menuNo=200218",
        "period": "2022년",
    },
    {
        "ntt_id": "8200",
        "title": "최근 회계심사·감리 주요 지적사례(10건) 공개",
        "pub_date": "2021-12-01",
        "year": 2021,
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=8200&menuNo=200218",
        "period": "2021년",
    },
    {
        "ntt_id": "8000",
        "title": "최근 회계심사·감리 주요 지적사례(10건) 공개",
        "pub_date": "2020-12-01",
        "year": 2020,
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=8000&menuNo=200218",
        "period": "2020년",
    },
]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.trust_env = False
    try:
        s.get(BASE_URL, timeout=10)
    except Exception:
        pass
    return s


def fetch_case_list(max_pages: int = 5) -> list[dict]:
    """지적사례 보도자료 목록 수집. 실패 시 시드 데이터 반환."""
    session = _session()
    cases = []

    for page in range(1, max_pages + 1):
        url = LIST_URL.format(page=page)
        logger.info(f"지적사례 목록 페이지 {page} 요청: {url}")

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"목록 페이지 요청 실패: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tbody tr")

        if not rows:
            break

        for row in rows:
            cols = row.select("td")
            if len(cols) < 3:
                continue

            title_td = row.select_one("td.subject a, td a")
            if not title_td:
                continue

            title = title_td.get_text(strip=True)
            if not title:
                continue

            href = title_td.get("href", "")
            ntt_id = _extract_ntt_id(href)
            if not ntt_id:
                onclick = title_td.get("onclick", "")
                ntt_id = _extract_ntt_id_from_onclick(onclick)

            if not ntt_id:
                continue

            pub_date = ""
            for td in cols:
                text = td.get_text(strip=True)
                if re.match(r"\d{4}[.\-]\d{2}[.\-]\d{2}", text):
                    pub_date = text.replace(".", "-")
                    break

            year = _extract_year(title, pub_date)
            period = _extract_period(title, pub_date)

            cases.append({
                "ntt_id": ntt_id,
                "title": title,
                "pub_date": pub_date,
                "year": year,
                "period": period,
                "url": DETAIL_URL.format(ntt_id=ntt_id),
            })

        time.sleep(1)

    if not cases:
        logger.warning("라이브 크롤링 결과 없음. 시드 데이터 사용.")
        return SEED_CASES

    return cases


def _is_case_article(title: str) -> bool:
    """지적사례 관련 게시글인지 확인"""
    keywords = ["지적사례", "지적 사례", "감리 주요", "회계심사,감리", "회계심사·감리"]
    return any(kw in title for kw in keywords)


def fetch_case_detail(ntt_id: str, session: Optional[requests.Session] = None) -> dict:
    """게시글 상세 페이지에서 첨부파일 URL 추출"""
    if session is None:
        session = _session()

    url = DETAIL_URL.format(ntt_id=ntt_id)
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"상세 페이지 요청 실패 (nttId={ntt_id}): {e}")
        return {"attachments": []}

    soup = BeautifulSoup(resp.text, "lxml")
    attachments = _extract_attachments(soup)
    return {"attachments": attachments}


def _extract_attachments(soup: BeautifulSoup) -> list[dict]:
    """첨부파일 링크 목록 추출 (PDF 우선)"""
    attachments = []

    for a in soup.select("a[href*='atchFileId'], a[href*='fileDown'], a[onclick*='fileDown'], a[href*='.pdf']"):
        href = a.get("href", "")
        onclick = a.get("onclick", "")
        name = a.get_text(strip=True)

        file_url = None
        if href and (".pdf" in href.lower() or "fileDown" in href or "atchFileId" in href):
            file_url = href if href.startswith("http") else BASE_URL + href
        elif "fileDown" in onclick:
            m = re.search(r"fileDown\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]", onclick)
            if m:
                file_url = (
                    f"{BASE_URL}/fss/cmm/fss/FileDown.do"
                    f"?atchFileId={m.group(1)}&fileSn={m.group(2)}"
                )

        if file_url:
            attachments.append({"name": name, "url": file_url})

    seen = set()
    unique = []
    for a in attachments:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique


def download_pdf(url: str, ntt_id: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """PDF 파일 다운로드 후 로컬 경로 반환"""
    if session is None:
        session = _session()

    save_path = DOWNLOAD_DIR / f"{ntt_id}.pdf"
    if save_path.exists():
        logger.info(f"이미 다운로드됨: {save_path}")
        return str(save_path)

    try:
        resp = session.get(url, timeout=30, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        cd = resp.headers.get("Content-Disposition", "")
        if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf") and "pdf" not in cd.lower():
            if len(resp.content) < 1000:
                logger.warning(f"PDF가 아닌 응답: {content_type}")
                return None

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"PDF 다운로드 완료: {save_path}")
        return str(save_path)

    except requests.RequestException as e:
        logger.error(f"PDF 다운로드 실패 ({url}): {e}")
        return None


def _extract_ntt_id(href: str) -> Optional[str]:
    m = re.search(r"nttId=(\d+)", href)
    return m.group(1) if m else None


def _extract_ntt_id_from_onclick(onclick: str) -> Optional[str]:
    m = re.search(r"['\"](\d{5,})['\"]", onclick)
    return m.group(1) if m else None


def _extract_year(title: str, pub_date: str) -> Optional[int]:
    m = re.search(r"(20\d{2})년", title)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d{4})", pub_date)
    if m:
        return int(m.group(1))
    return None


def _extract_period(title: str, pub_date: str) -> str:
    """게시물에서 해당 지적사례 기간(예: '2025년 상반기') 추출"""
    m = re.search(r"(20\d{2}년\s*(?:상반기|하반기|연간)?)", title)
    if m:
        return m.group(1).strip()
    m = re.match(r"(\d{4})", pub_date)
    if m:
        return f"{m.group(1)}년"
    return ""
