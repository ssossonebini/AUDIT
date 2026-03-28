"""
한국회계기준원(KASB) K-IFRS 제·개정 현황 크롤러
- 제·개정 자료 게시판(bbsCd=1061) 목록 수집
- 각 게시글의 첨부 PDF 다운로드
- 크롤링 실패 시 시드 데이터 반환
"""
import re
import time
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "http://www.kasb.or.kr"
LIST_URL = (
    "http://www.kasb.or.kr/fe/bbs/NR_list.do"
    "?bbsCd=1061&currentPage={page}&rowPerPage=20&ctgCd=&searchKey=1000&searchVal="
)
DETAIL_URL = (
    "http://www.kasb.or.kr/fe/bbs/NR_view.do"
    "?bbsCd=1061&bbsSeq={bbs_seq}"
)

DOWNLOAD_DIR = Path("downloads/kasb")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "http://www.kasb.or.kr/",
}

# ────────────────────────────────────────────────────────────────
# 시드 데이터: K-IFRS 주요 제·개정 현황 (2022~2027)
# 출처: KASB 공시 및 IFRS Foundation 기준 정리
# ────────────────────────────────────────────────────────────────
SEED_STANDARDS = [
    # ── 신규 제정 ──────────────────────────────────────────────
    {
        "standard_id": "kifrs-1118-new-2024",
        "standard_number": "K-IFRS 제1118호",
        "standard_name": "재무제표 표시 및 공시",
        "amendment_type": "신규제정",
        "category": "K-IFRS",
        "issued_date": "2024-11-01",
        "effective_date": "2027-01-01",
        "effective_year": 2027,
        "early_adoption": True,
        "replaced_standard": "K-IFRS 제1001호",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "IAS 1(K-IFRS 제1001호)을 대체하는 IFRS 18 도입. "
            "손익계산서 구조 개편(영업이익 필수 표시), 경영성과지표(MPM) 공시 의무화, "
            "집합 및 분해 원칙 강화. 2027년 1월 1일 이후 시작하는 회계연도부터 적용 (조기적용 가능)."
        ),
    },
    {
        "standard_id": "kifrs-1117-new-2023",
        "standard_number": "K-IFRS 제1117호",
        "standard_name": "보험계약",
        "amendment_type": "신규제정",
        "category": "K-IFRS",
        "issued_date": "2017-05-01",
        "effective_date": "2023-01-01",
        "effective_year": 2023,
        "early_adoption": True,
        "replaced_standard": "K-IFRS 제1104호",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "IFRS 4(K-IFRS 제1104호)를 대체. 모든 보험계약에 단일 회계모형 적용 "
            "(일반모형·보험료배분접근법·변동수수료접근법). 보험부채를 현재 추정치로 측정하고 "
            "보험서비스결과와 금융성과를 분리 표시. 보험업 대상 획기적 변경."
        ),
    },
    # ── 2024년 시행 개정 ──────────────────────────────────────
    {
        "standard_id": "kifrs-1001-amendment-2023-liab",
        "standard_number": "K-IFRS 제1001호 개정",
        "standard_name": "재무제표 표시 — 유동부채와 비유동부채의 분류",
        "amendment_type": "개정",
        "category": "K-IFRS",
        "issued_date": "2020-01-23",
        "effective_date": "2024-01-01",
        "effective_year": 2024,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "유동/비유동 분류 기준을 보고기간 말 현재 존재하는 권리에 한정. "
            "결제 조건이 부수된 약정(covenant) 위반 시 비유동 분류 유지 조건 명확화. "
            "전환사채 등 자기지분상품으로 결제 가능한 부채의 분류 기준 정비."
        ),
    },
    {
        "standard_id": "kifrs-1007-1107-amendment-2023-supplier",
        "standard_number": "K-IFRS 제1007호·제1107호 개정",
        "standard_name": "현금흐름표·금융상품 공시 — 공급자금융약정",
        "amendment_type": "개정",
        "category": "K-IFRS",
        "issued_date": "2023-05-01",
        "effective_date": "2024-01-01",
        "effective_year": 2024,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "공급자금융약정(역팩토링 포함)에 대한 공시 요구사항 신설. "
            "약정 조건·장부금액·유동성 위험 영향 등을 공시. "
            "매입채무의 공급자금융약정으로의 재분류 여부 판단 필요."
        ),
    },
    {
        "standard_id": "kifrs-1116-amendment-2023-leaseback",
        "standard_number": "K-IFRS 제1116호 개정",
        "standard_name": "리스 — 판매후리스에서의 리스부채",
        "amendment_type": "개정",
        "category": "K-IFRS",
        "issued_date": "2022-09-01",
        "effective_date": "2024-01-01",
        "effective_year": 2024,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "판매후리스 거래에서 판매자-리스이용자가 리스부채를 측정하는 방법 명확화. "
            "리스료 중 미래 사용권에 해당하는 부분만 리스부채에 포함. "
            "이익 또는 손실은 구매자-리스제공자에게 이전된 권리에만 인식."
        ),
    },
    {
        "standard_id": "kifrs-annual-improvement-2021-2023",
        "standard_number": "K-IFRS 연차개선 2021-2023",
        "standard_name": "연차개선 — K-IFRS 제1101호·제1016호·제1117호",
        "amendment_type": "개정",
        "category": "K-IFRS",
        "issued_date": "2022-10-01",
        "effective_date": "2024-01-01",
        "effective_year": 2024,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "K-IFRS 제1101호(최초 채택): 누적환산차이 회계처리 명확화. "
            "K-IFRS 제1016호(유형자산): 의도한 방식으로 사용 가능 전 생산된 재화의 처리. "
            "K-IFRS 제1117호(보험계약): 금융요소가 중요하지 않은 계약에서 보험취득 현금흐름 처리."
        ),
    },
    # ── 2025년 시행 개정 ──────────────────────────────────────
    {
        "standard_id": "kifrs-1021-1101-amendment-2024-exchange",
        "standard_number": "K-IFRS 제1021호·제1101호 개정",
        "standard_name": "환율변동효과·외화환산 — 교환가능성 결여",
        "amendment_type": "개정",
        "category": "K-IFRS",
        "issued_date": "2023-08-01",
        "effective_date": "2025-01-01",
        "effective_year": 2025,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "한 통화를 다른 통화로 교환할 수 없는 경우(교환가능성 결여) 적용할 환율 결정 방법 제시. "
            "교환가능성 판단 절차 및 교환가능성 결여 시 추정환율 산정 방법 명확화. "
            "공시: 교환가능성 결여 통화에 대한 유동성 위험 정보 추가 요구."
        ),
    },
    {
        "standard_id": "kifrs-annual-improvement-2022-2024",
        "standard_number": "K-IFRS 연차개선 2022-2024",
        "standard_name": "연차개선 — K-IFRS 제1101호·제1109호·제1107호·제1034호",
        "amendment_type": "개정",
        "category": "K-IFRS",
        "issued_date": "2024-07-01",
        "effective_date": "2025-01-01",
        "effective_year": 2025,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "K-IFRS 제1101호: 지배기업의 최초 채택 면제 적용. "
            "K-IFRS 제1109호: 금융부채 제거 요건 — 10% 테스트 시 수수료 처리. "
            "K-IFRS 제1107호: 위험 집중도 공시. "
            "K-IFRS 제1034호: 중간재무보고 — 부문별 정보 공시."
        ),
    },
    # ── 2026년 시행 개정 ──────────────────────────────────────
    {
        "standard_id": "kifrs-1109-1107-amendment-2024-classification",
        "standard_number": "K-IFRS 제1109호·제1107호 개정",
        "standard_name": "금융상품 — 분류 및 측정",
        "amendment_type": "개정",
        "category": "K-IFRS",
        "issued_date": "2023-05-01",
        "effective_date": "2026-01-01",
        "effective_year": 2026,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "금융자산 분류 요건 중 사업모형 및 현금흐름 특성 평가 명확화. "
            "공정가치로 측정하는 지분상품 투자의 공시 요구 강화. "
            "결제조건이 있는 금융부채의 분류 기준 개정. "
            "전자화폐 관련 계약의 금융상품 해당 여부 판단 지침 추가."
        ),
    },
    # ── 2027년 시행 (IFRS 18 관련 추가 개정) ──────────────────
    {
        "standard_id": "kifrs-various-amendment-2024-ifrs18-consequential",
        "standard_number": "K-IFRS 다수 기준서 개정 (IFRS 18 후속 개정)",
        "standard_name": "K-IFRS 제1007호·제1033호·제1034호 등 — IFRS 18 후속 개정",
        "amendment_type": "개정",
        "category": "K-IFRS",
        "issued_date": "2024-11-01",
        "effective_date": "2027-01-01",
        "effective_year": 2027,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "IFRS 18(K-IFRS 제1118호) 도입에 따른 다수 기준서 후속 개정. "
            "현금흐름표(제1007호), 주당이익(제1033호), 중간재무보고(제1034호) 등에서 "
            "손익계산서 구조 변경 및 경영성과지표(MPM) 관련 참조 조항 정비."
        ),
    },
    # ── 지속가능성 공시 기준 (ISSB) ────────────────────────────
    {
        "standard_id": "ifrs-s1-sustainability-2023",
        "standard_number": "IFRS S1",
        "standard_name": "지속가능성 관련 재무정보 공시에 관한 일반 요구사항",
        "amendment_type": "신규제정",
        "category": "ISSB",
        "issued_date": "2023-06-26",
        "effective_date": "2024-01-01",
        "effective_year": 2024,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "지속가능성 관련 위험 및 기회에 대한 공시 프레임워크 제공. "
            "핵심공시(거버넌스·전략·위험관리·지표 및 목표) 4개 영역 요구. "
            "국내 적용 시기는 금융위·금감원 별도 공시 기준에 따름."
        ),
    },
    {
        "standard_id": "ifrs-s2-climate-2023",
        "standard_number": "IFRS S2",
        "standard_name": "기후 관련 공시",
        "amendment_type": "신규제정",
        "category": "ISSB",
        "issued_date": "2023-06-26",
        "effective_date": "2024-01-01",
        "effective_year": 2024,
        "early_adoption": True,
        "replaced_standard": "",
        "url": "https://www.kasb.or.kr/fe/accstd/NR_list.do",
        "pdf_url": "",
        "description": (
            "TCFD 권고안을 기반으로 한 기후 관련 위험 및 기회의 공시 요구. "
            "물리적 위험(기상이변·만성 기후변화)과 전환 위험(정책·기술·시장) 구분. "
            "Scope 1·2·3 온실가스 배출량 공시. "
            "국내 의무 적용 시기는 별도 확정 예정."
        ),
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


def fetch_standard_list(max_pages: int = 5) -> list[dict]:
    """KASB 제·개정 자료 목록 수집. 실패 시 시드 데이터 반환."""
    session = _session()
    standards = []

    for page in range(1, max_pages + 1):
        url = LIST_URL.format(page=page)
        logger.info(f"KASB 목록 페이지 {page} 요청: {url}")

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            if resp.status_code == 403:
                logger.warning("KASB 403 응답. 시드 데이터 사용.")
                break
        except requests.RequestException as e:
            logger.error(f"KASB 목록 요청 실패: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tbody tr")

        if not rows:
            break

        page_items = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 3:
                continue

            title_td = row.select_one("td a")
            if not title_td:
                continue

            title = title_td.get_text(strip=True)
            if not title:
                continue

            href = title_td.get("href", "")
            bbs_seq = _extract_bbs_seq(href)
            if not bbs_seq:
                onclick = title_td.get("onclick", "")
                bbs_seq = _extract_bbs_seq_onclick(onclick)

            if not bbs_seq:
                continue

            pub_date = ""
            for td in cols:
                text = td.get_text(strip=True)
                if re.match(r"\d{4}[.\-]\d{2}[.\-]\d{2}", text):
                    pub_date = text.replace(".", "-")
                    break

            # 발효일은 상세 페이지에서 추출해야 하므로 여기서는 게시일을 사용
            year = int(pub_date[:4]) if pub_date else None

            page_items.append({
                "standard_id": f"kasb-{bbs_seq}",
                "standard_number": _guess_standard_number(title),
                "standard_name": title,
                "amendment_type": _guess_amendment_type(title),
                "category": "K-IFRS",
                "issued_date": pub_date,
                "effective_date": "",
                "effective_year": year,
                "early_adoption": False,
                "replaced_standard": "",
                "url": f"{BASE_URL}/fe/bbs/NR_view.do?bbsCd=1061&bbsSeq={bbs_seq}",
                "pdf_url": "",
                "description": "",
            })

        if not page_items:
            break

        standards.extend(page_items)
        time.sleep(1)

    if not standards:
        logger.warning("KASB 라이브 크롤링 결과 없음. 시드 데이터 사용.")
        return SEED_STANDARDS

    return standards


def fetch_detail(bbs_seq: str, session: Optional[requests.Session] = None) -> dict:
    """게시글 상세 페이지에서 첨부파일 URL 추출"""
    if session is None:
        session = _session()

    url = DETAIL_URL.format(bbs_seq=bbs_seq)
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"KASB 상세 페이지 요청 실패 ({bbs_seq}): {e}")
        return {"attachments": [], "effective_date": ""}

    soup = BeautifulSoup(resp.text, "lxml")
    attachments = _extract_attachments(soup)
    effective_date = _extract_effective_date(soup)

    return {"attachments": attachments, "effective_date": effective_date}


def _extract_attachments(soup: BeautifulSoup) -> list[dict]:
    attachments = []
    for a in soup.select("a[href*='.pdf'], a[href*='download'], a[href*='fileDown']"):
        href = a.get("href", "")
        name = a.get_text(strip=True)
        if not href:
            continue
        file_url = href if href.startswith("http") else BASE_URL + href
        attachments.append({"name": name, "url": file_url})

    seen = set()
    unique = []
    for a in attachments:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique


def _extract_effective_date(soup: BeautifulSoup) -> str:
    """본문 내 시행일 추출 시도"""
    text = soup.get_text()
    patterns = [
        r"시행일[^\d]*(20\d{2}[.\-]\d{2}[.\-]\d{2})",
        r"적용일[^\d]*(20\d{2}[.\-]\d{2}[.\-]\d{2})",
        r"효력발생[^\d]*(20\d{2}[.\-]\d{2}[.\-]\d{2})",
        r"(20\d{2})[^\d]*년\s*(\d{1,2})[^\d]*월\s*(\d{1,2})[^\d]*일.*시행",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).replace(".", "-")
    return ""


def download_pdf(url: str, standard_id: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """PDF 다운로드 후 로컬 경로 반환"""
    if session is None:
        session = _session()

    safe_id = re.sub(r"[^\w\-]", "_", standard_id)
    save_path = DOWNLOAD_DIR / f"{safe_id}.pdf"
    if save_path.exists():
        logger.info(f"이미 다운로드됨: {save_path}")
        return str(save_path)

    try:
        resp = session.get(url, timeout=60, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        cd = resp.headers.get("Content-Disposition", "")
        is_pdf = (
            "pdf" in content_type.lower()
            or url.lower().endswith(".pdf")
            or "pdf" in cd.lower()
        )
        if not is_pdf and len(resp.content) < 1000:
            logger.warning(f"PDF가 아닌 응답: {content_type}")
            return None

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"KASB PDF 다운로드 완료: {save_path}")
        return str(save_path)

    except requests.RequestException as e:
        logger.error(f"KASB PDF 다운로드 실패 ({url}): {e}")
        return None


def _extract_bbs_seq(href: str) -> Optional[str]:
    m = re.search(r"bbsSeq=(\d+)", href)
    return m.group(1) if m else None


def _extract_bbs_seq_onclick(onclick: str) -> Optional[str]:
    m = re.search(r"['\"](\d{4,})['\"]", onclick)
    return m.group(1) if m else None


def _guess_standard_number(title: str) -> str:
    """제목에서 기준서 번호 추출 시도"""
    m = re.search(r"K-IFRS\s*제\d+호|K-IFRS\s*\d+|IFRS\s*[A-Z]?\d+", title)
    return m.group(0) if m else ""


def _guess_amendment_type(title: str) -> str:
    if re.search(r"신규|제정|도입", title):
        return "신규제정"
    if re.search(r"개정|수정", title):
        return "개정"
    if re.search(r"해석|질의", title):
        return "해석서"
    return "개정"
