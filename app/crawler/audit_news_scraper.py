"""
금융감독원(FSS) + 금융위원회(FSC) 보도자료 크롤러
- 2025-01-01 이후 전체 보도자료 수집
- 증분 크롤링: 마지막 수집일 이후 신규 게시물만 처리
- 1단계 키워드 사전 필터 → 2단계 Claude AI 분류
- 회계감사·감사보고서 관련 항목만 DB 저장
"""
import json
import re
import time
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── FSS ──────────────────────────────────────────────────────────
FSS_BASE    = "https://www.fss.or.kr"
FSS_LIST_URL = (
    "https://www.fss.or.kr/fss/bbs/B0000188/list.do"
    "?menuNo=200218&bbsId=&cl1Cd=&pageIndex={page}"
    "&sdate={sdate}&edate=&searchCnd=0&searchWrd="
)
FSS_DETAIL_URL = "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId={ntt_id}&menuNo=200218"

# ── FSC ──────────────────────────────────────────────────────────
FSC_BASE     = "https://www.fsc.go.kr"
FSC_LIST_URL = (
    "https://www.fsc.go.kr/no010101"
    "?curPage={page}&srchBeginDt={sdate}&srchEndDt="
    "&srchKey=sj&srchText="
)
FSC_DETAIL_URL = "https://www.fsc.go.kr/no010101/{article_id}"

DEFAULT_START_DATE = "2025-01-01"

DOWNLOAD_DIR = Path("downloads/audit_news")
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
}

# ── 키워드 사전 필터 ──────────────────────────────────────────────
# 이 키워드 중 하나라도 포함되면 AI 분류 대상으로 올림
AUDIT_INCLUDE_KEYWORDS = [
    "회계", "감사", "재무제표", "IFRS", "K-IFRS",
    "내부통제", "내부회계관리", "감리",
    "외감", "공시", "감사인", "회계법인",
    "분식", "회계기준", "외부감사", "감사보고서",
    "회계처리", "공인회계사", "회계감리",
]

# 이 키워드가 제목에 있으면 명백히 무관 → AI 호출 없이 즉시 제외
AUDIT_EXCLUDE_KEYWORDS = [
    "가계대출", "주택담보대출", "보이스피싱", "불법사금융",
    "보험사기", "카드수수료", "소비자피해", "불법대출",
    "대출금리", "예금금리", "보험료", "자동차보험",
    "보이스피싱", "스미싱", "파밍",
]


def _session(base_url: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.headers["Referer"] = base_url
    s.trust_env = False
    try:
        s.get(base_url, timeout=10)
    except Exception:
        pass
    return s


# ════════════════════════════════════════════════════════════════
# 키워드 필터
# ════════════════════════════════════════════════════════════════

def keyword_filter(title: str) -> bool:
    """
    True  = AI 분류 필요 (관련 가능성 있음)
    False = 즉시 제외 (명백히 무관)
    """
    for kw in AUDIT_EXCLUDE_KEYWORDS:
        if kw in title:
            return False
    for kw in AUDIT_INCLUDE_KEYWORDS:
        if kw in title:
            return True
    return False  # 포함 키워드 없으면 제외


# ════════════════════════════════════════════════════════════════
# FSS 크롤러
# ════════════════════════════════════════════════════════════════

def fetch_fss_news(sdate: str, max_pages: int, existing_ids: set) -> list[dict]:
    """
    FSS 보도자료 수집.
    - sdate 이후 게시물만 요청
    - existing_ids에 있는 ntt_id 발견 시 즉시 중단 (증분 크롤링)
    - 키워드 필터 통과 항목만 반환
    """
    session = _session(FSS_BASE)
    results = []

    for page in range(1, max_pages + 1):
        url = FSS_LIST_URL.format(page=page, sdate=sdate)
        logger.info(f"[FSS] 페이지 {page} 요청: {url}")

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[FSS] 요청 실패: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tbody tr")
        if not rows:
            break

        stop = False
        for row in rows:
            cols = row.select("td")
            if len(cols) < 3:
                continue

            title_td = row.select_one("td.subject a, td a")
            if not title_td:
                continue

            title = title_td.get_text(strip=True)
            href  = title_td.get("href", "")
            ntt_id = _extract_param(href, "nttId")
            if not ntt_id:
                ntt_id = _extract_ntt_id_onclick(title_td.get("onclick", ""))
            if not ntt_id:
                continue

            # 기존 레코드 발견 → 증분 중단
            uid = f"FSS-{ntt_id}"
            if uid in existing_ids:
                logger.info(f"[FSS] 기존 레코드 발견 ({ntt_id}). 증분 중단.")
                stop = True
                break

            pub_date = _extract_date_from_row(cols)
            if pub_date and pub_date < sdate:
                stop = True
                break

            if not keyword_filter(title):
                continue

            results.append({
                "source":   "FSS",
                "ntt_id":   f"FSS-{ntt_id}",
                "title":    title,
                "pub_date": pub_date,
                "year":     int(pub_date[:4]) if pub_date else None,
                "url":      FSS_DETAIL_URL.format(ntt_id=ntt_id),
                "department": _extract_department(cols),
            })

        if stop:
            break
        time.sleep(0.8)

    return results


# ════════════════════════════════════════════════════════════════
# FSC 크롤러
# ════════════════════════════════════════════════════════════════

def fetch_fsc_news(sdate: str, max_pages: int, existing_ids: set) -> list[dict]:
    """FSC 보도자료 수집 (FSS와 동일 구조)"""
    session = _session(FSC_BASE)
    results = []

    for page in range(1, max_pages + 1):
        url = FSC_LIST_URL.format(page=page, sdate=sdate)
        logger.info(f"[FSC] 페이지 {page} 요청: {url}")

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[FSC] 요청 실패 (403 등): {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")

        # FSC는 table 또는 ul/li 구조일 수 있어 두 패턴 모두 시도
        rows = soup.select("table tbody tr") or soup.select("ul.boardList li")
        if not rows:
            break

        stop = False
        for row in rows:
            # table row 방식
            title_td = row.select_one("td.subject a, td.title a, td a")
            if not title_td:
                # li 방식
                title_td = row.select_one("a")
            if not title_td:
                continue

            title = title_td.get_text(strip=True)
            href  = title_td.get("href", "")

            # FSC article_id 추출: /no010101/12345 패턴
            article_id = _extract_fsc_id(href)
            if not article_id:
                continue

            uid = f"FSC-{article_id}"
            if uid in existing_ids:
                logger.info(f"[FSC] 기존 레코드 발견 ({article_id}). 증분 중단.")
                stop = True
                break

            cols = row.select("td")
            pub_date = _extract_date_from_row(cols)
            if pub_date and pub_date < sdate:
                stop = True
                break

            if not keyword_filter(title):
                continue

            results.append({
                "source":     "FSC",
                "ntt_id":     uid,
                "title":      title,
                "pub_date":   pub_date,
                "year":       int(pub_date[:4]) if pub_date else None,
                "url":        FSC_DETAIL_URL.format(article_id=article_id),
                "department": _extract_department(cols),
            })

        if stop:
            break
        time.sleep(0.8)

    return results


# ════════════════════════════════════════════════════════════════
# PDF 다운로드
# ════════════════════════════════════════════════════════════════

def fetch_fss_attachments(ntt_id_raw: str,
                          session: Optional[requests.Session] = None) -> list[dict]:
    """FSS 상세 페이지에서 첨부파일 URL 추출"""
    if session is None:
        session = _session(FSS_BASE)
    url = FSS_DETAIL_URL.format(ntt_id=ntt_id_raw)
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"FSS 상세 요청 실패: {e}")
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    return _extract_attachments(soup, FSS_BASE)


def fetch_fsc_attachments(article_id: str,
                          session: Optional[requests.Session] = None) -> list[dict]:
    """FSC 상세 페이지에서 첨부파일 URL 추출"""
    if session is None:
        session = _session(FSC_BASE)
    url = FSC_DETAIL_URL.format(article_id=article_id)
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"FSC 상세 요청 실패: {e}")
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    return _extract_attachments(soup, FSC_BASE)


def _extract_attachments(soup: BeautifulSoup, base: str) -> list[dict]:
    items = []
    for a in soup.select(
        "a[href*='.pdf'], a[href*='fileDown'], a[href*='atchFileId'], "
        "a[href*='download'], a[onclick*='fileDown']"
    ):
        href   = a.get("href", "")
        onclick = a.get("onclick", "")
        name   = a.get_text(strip=True)
        url    = None

        if href and (".pdf" in href.lower() or "fileDown" in href
                     or "atchFileId" in href or "download" in href):
            url = href if href.startswith("http") else base + href
        elif "fileDown" in onclick:
            m = re.search(
                r"fileDown\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]", onclick
            )
            if m:
                url = (
                    f"{FSS_BASE}/fss/cmm/fss/FileDown.do"
                    f"?atchFileId={m.group(1)}&fileSn={m.group(2)}"
                )
        if url:
            items.append({"name": name, "url": url})

    seen, unique = set(), []
    for i in items:
        if i["url"] not in seen:
            seen.add(i["url"])
            unique.append(i)
    return unique


def download_pdf(url: str, uid: str,
                 session: Optional[requests.Session] = None) -> Optional[str]:
    if session is None:
        session = _session(FSS_BASE)

    safe = re.sub(r"[^\w\-]", "_", uid)
    path = DOWNLOAD_DIR / f"{safe}.pdf"
    if path.exists():
        return str(path)

    try:
        resp = session.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")
        cd = resp.headers.get("Content-Disposition", "")
        if ("pdf" not in ct.lower() and not url.lower().endswith(".pdf")
                and "pdf" not in cd.lower() and len(resp.content) < 1000):
            return None
        with open(path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return str(path)
    except requests.RequestException as e:
        logger.error(f"PDF 다운로드 실패 ({url}): {e}")
        return None


# ════════════════════════════════════════════════════════════════
# 유틸
# ════════════════════════════════════════════════════════════════

def _extract_param(url: str, param: str) -> Optional[str]:
    m = re.search(rf"{param}=(\w+)", url)
    return m.group(1) if m else None


def _extract_ntt_id_onclick(onclick: str) -> Optional[str]:
    m = re.search(r"['\"](\d{5,})['\"]", onclick)
    return m.group(1) if m else None


def _extract_fsc_id(href: str) -> Optional[str]:
    # /no010101/85959 패턴
    m = re.search(r"/no010101/(\d+)", href)
    return m.group(1) if m else None


def _extract_date_from_row(cols) -> str:
    for td in cols:
        text = td.get_text(strip=True)
        # YYYY.MM.DD 또는 YYYY-MM-DD
        m = re.search(r"(20\d{2})[.\-](\d{2})[.\-](\d{2})", text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # YYMMDD (FSC 형식: 260316)
        m2 = re.match(r"^(\d{2})(\d{2})(\d{2})$", text.strip())
        if m2:
            yy = int(m2.group(1))
            year = 2000 + yy if yy < 50 else 1900 + yy
            return f"{year}-{m2.group(2)}-{m2.group(3)}"
    return ""


def _extract_department(cols) -> str:
    for td in cols:
        text = td.get_text(strip=True)
        if re.search(r"국$|과$|팀$|실$|원$", text) and len(text) < 20:
            return text
    return ""
