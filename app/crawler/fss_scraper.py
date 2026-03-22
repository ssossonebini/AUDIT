"""
금융감독원 보도자료 크롤러
- 중점심사 회계이슈 사전예고 보도자료 목록 수집
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
LIST_URL = (
    "https://www.fss.or.kr/fss/bbs/B0000188/list.do"
    "?menuNo=200218&bbsId=&cl1Cd=&pageIndex={page}"
    "&sdate=&edate=&searchCnd=1&searchWrd=%EC%A4%91%EC%A0%90%EC%8B%AC%EC%82%AC"
)
DETAIL_URL = "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId={ntt_id}&menuNo=200218"

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

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


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    # 시스템 프록시 무시 (직접 연결)
    s.trust_env = False
    # 첫 요청으로 세션 쿠키 획득
    try:
        s.get(BASE_URL, timeout=10)
    except Exception:
        pass
    return s


def fetch_article_list(max_pages: int = 5) -> list[dict]:
    """보도자료 목록 페이지를 순회하며 게시글 메타데이터 수집"""
    session = _session()
    articles = []

    for page in range(1, max_pages + 1):
        url = LIST_URL.format(page=page)
        logger.info(f"목록 페이지 {page} 요청: {url}")

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"목록 페이지 요청 실패: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tbody tr")

        if not rows:
            # 결과 없음 또는 마지막 페이지
            break

        page_articles = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 3:
                continue

            # 제목 링크
            title_td = row.select_one("td.subject a, td a")
            if not title_td:
                continue

            title = title_td.get_text(strip=True)
            href = title_td.get("href", "")

            # nttId 추출
            ntt_id = _extract_ntt_id(href)
            if not ntt_id:
                # onclick 속성에서 추출 시도
                onclick = title_td.get("onclick", "")
                ntt_id = _extract_ntt_id_from_onclick(onclick)

            if not ntt_id:
                continue

            # 게시일
            pub_date = ""
            for td in cols:
                text = td.get_text(strip=True)
                if re.match(r"\d{4}[.\-]\d{2}[.\-]\d{2}", text):
                    pub_date = text.replace(".", "-")
                    break

            year = _extract_year(title, pub_date)

            detail_url = DETAIL_URL.format(ntt_id=ntt_id)
            page_articles.append({
                "ntt_id": ntt_id,
                "title": title,
                "pub_date": pub_date,
                "year": year,
                "url": detail_url,
            })

        if not page_articles:
            break

        articles.extend(page_articles)
        time.sleep(1)  # 서버 부하 방지

    return articles


def fetch_article_detail(ntt_id: str, session: Optional[requests.Session] = None) -> dict:
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
    attachments = _extract_attachments(soup, session)

    return {"attachments": attachments}


def _extract_attachments(soup: BeautifulSoup, session: requests.Session) -> list[dict]:
    """첨부파일 링크 목록 추출"""
    attachments = []

    # 다양한 첨부파일 링크 패턴 탐색
    for a in soup.select("a[href*='atchFileId'], a[href*='fileDown'], a[onclick*='fileDown'], a[href*='.pdf']"):
        href = a.get("href", "")
        onclick = a.get("onclick", "")
        name = a.get_text(strip=True)

        file_url = None
        if href and (".pdf" in href.lower() or "fileDown" in href or "atchFileId" in href):
            file_url = href if href.startswith("http") else BASE_URL + href
        elif "fileDown" in onclick:
            # onclick="fileDown('atchFileId','fileSn')" 패턴
            m = re.search(r"fileDown\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]", onclick)
            if m:
                file_url = (
                    f"{BASE_URL}/fss/cmm/fss/FileDown.do"
                    f"?atchFileId={m.group(1)}&fileSn={m.group(2)}"
                )

        if file_url:
            attachments.append({"name": name, "url": file_url})

    # 중복 제거
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
        if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
            # 직접 URL이 아닌 경우 Content-Disposition 헤더 확인
            cd = resp.headers.get("Content-Disposition", "")
            if "pdf" not in cd.lower() and len(resp.content) < 1000:
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
    """제목 또는 게시일에서 연도 추출"""
    # 제목에서 연도 추출 (예: "2024년도", "2024년 재무제표")
    m = re.search(r"(20\d{2})년", title)
    if m:
        return int(m.group(1))
    # 게시일에서 연도 추출
    m = re.match(r"(\d{4})", pub_date)
    if m:
        return int(m.group(1))
    return None
