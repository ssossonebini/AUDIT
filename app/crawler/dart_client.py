"""OPEN DART API 클라이언트.

인증키는 settings.DART_API_KEY (.env) 에서 읽는다.

응답 형태에서 주의할 점 (CLAUDE.md 에도 기록):
- 3개년 금액은 reprt_code=11011(사업보고서)에서만 함께 온다.
  분기·반기는 bfefrmtrm_* 키가 아예 없으므로 .get() 으로 접근해야 한다.
- 분기 손익계산서의 전기 금액은 frmtrm_amount 가 아니라 frmtrm_q_amount 다.
- 금액은 "9,999,999,999" 같은 문자열이고, 빈 값이 "" 또는 "-" 로 온다.
"""

import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://opendart.fss.or.kr/api"
CACHE_DIR = Path("downloads/dart")
CORP_CODE_FILE = CACHE_DIR / "CORPCODE.xml"

# 정기보고서 코드
REPRT_ANNUAL = "11011"   # 사업보고서 — 3개년 금액이 함께 오는 유일한 코드
REPRT_HALF = "11012"
REPRT_Q1 = "11013"
REPRT_Q3 = "11014"

TIMEOUT = 30

# status 000 정상 / 013 조회된 데이터 없음. 나머지는 오류로 다룬다.
STATUS_MESSAGES = {
    "010": "등록되지 않은 인증키입니다.",
    "011": "사용할 수 없는 인증키입니다. OPEN DART에서 상태를 확인하세요.",
    "012": "접근할 수 없는 IP입니다.",
    "013": "조회된 데이터가 없습니다.",
    "014": "파일이 존재하지 않습니다.",
    "020": "요청 제한을 초과했습니다 (일 20,000건).",
    "021": "조회 가능한 회사 개수가 초과했습니다.",
    "100": "필드의 부적절한 값입니다.",
    "101": "부적절한 접근입니다.",
    "800": "시스템 점검 중입니다.",
    "900": "정의되지 않은 오류가 발생했습니다.",
    "901": "사용자 계정의 개인정보 보유기간이 만료되었습니다.",
}


class DartError(RuntimeError):
    """DART가 정상(000)이 아닌 status 를 돌려준 경우."""

    def __init__(self, status: str, message: str = ""):
        self.status = status
        self.message = message or STATUS_MESSAGES.get(status, "알 수 없는 오류")
        super().__init__(f"[{status}] {self.message}")


def _require_key() -> str:
    key = settings.DART_API_KEY
    if not key:
        raise DartError("010", "DART_API_KEY가 .env에 설정되지 않았습니다.")
    return key


def _get(endpoint: str, **params) -> dict:
    """DART JSON 엔드포인트 호출. status 를 검사해 예외로 바꾼다."""
    params["crtfc_key"] = _require_key()
    resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()

    data = resp.json()
    status = data.get("status", "000")
    if status != "000":
        raise DartError(status, data.get("message", ""))
    return data


# ── 고유번호(corp_code) ────────────────────────────────────────────

_corp_index: Optional[dict[str, list[dict]]] = None


def download_corp_codes(force: bool = False) -> Path:
    """전체 고유번호 파일을 내려받아 캐시한다 (ZIP 안에 CORPCODE.xml)."""
    if CORP_CODE_FILE.exists() and not force:
        return CORP_CODE_FILE

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(
        f"{BASE_URL}/corpCode.xml", params={"crtfc_key": _require_key()}, timeout=60
    )
    resp.raise_for_status()

    # 오류일 때는 ZIP 이 아니라 XML/JSON 이 온다
    if not resp.content.startswith(b"PK"):
        status = re.search(rb"<status>(\d+)</status>", resp.content)
        raise DartError(status.group(1).decode() if status else "900")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = next(n for n in zf.namelist() if n.upper().endswith(".XML"))
        CORP_CODE_FILE.write_bytes(zf.read(name))

    logger.info(f"고유번호 파일 저장: {CORP_CODE_FILE}")
    return CORP_CODE_FILE


def _load_corp_index() -> dict[str, list[dict]]:
    """회사명 → 항목들. 동명 회사가 있으므로 값은 리스트다."""
    global _corp_index
    if _corp_index is not None:
        return _corp_index

    path = download_corp_codes()
    index: dict[str, list[dict]] = {}

    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "list":
            continue
        name = (elem.findtext("corp_name") or "").strip()
        if name:
            index.setdefault(name, []).append({
                "corp_code": (elem.findtext("corp_code") or "").strip(),
                "corp_name": name,
                "stock_code": (elem.findtext("stock_code") or "").strip(),
                "modify_date": (elem.findtext("modify_date") or "").strip(),
            })
        elem.clear()

    _corp_index = index
    logger.info(f"고유번호 {len(index):,}개 로드")
    return index


def search_corp(name: str, listed_only: bool = True, limit: int = 20) -> list[dict]:
    """회사명으로 검색한다. 정확히 일치하는 항목을 앞에 둔다.

    listed_only 면 stock_code 가 있는 상장사만 남긴다. DART에는 비상장
    법인이 대부분이라, 켜두지 않으면 동명 비상장사가 잔뜩 나온다.
    """
    query = name.strip()
    if not query:
        return []

    index = _load_corp_index()
    exact = list(index.get(query, []))
    partial = [
        item
        for key, items in index.items()
        if query in key and key != query
        for item in items
    ]

    results = exact + partial
    if listed_only:
        results = [r for r in results if r["stock_code"]]
    return results[:limit]


# ── 기업개황 / 재무제표 ────────────────────────────────────────────

def fetch_company(corp_code: str) -> dict:
    """기업개황 — 업종코드·대표자·결산월 등."""
    return _get("company.json", corp_code=corp_code)


def fetch_financials(
    corp_code: str,
    bsns_year: int,
    fs_div: str = "CFS",
    reprt_code: str = REPRT_ANNUAL,
) -> list[dict]:
    """단일회사 전체 재무제표.

    reprt_code=11011 이면 한 번의 호출로 당기·전기·전전기가 함께 온다.
    """
    data = _get(
        "fnlttSinglAcntAll.json",
        corp_code=corp_code,
        bsns_year=str(bsns_year),
        reprt_code=reprt_code,
        fs_div=fs_div,
    )
    return data.get("list", [])


FS_DIV_LABELS = {"CFS": "연결", "OFS": "별도"}


def fetch_all_divisions(
    corp_code: str, bsns_year: int, reprt_code: str = REPRT_ANNUAL
) -> dict[str, list[dict]]:
    """연결(CFS)과 별도(OFS)를 모두 받아온다.

    감사 대상은 별도재무제표인 경우가 많고, 연결과의 비교도 필요하므로
    둘 중 하나로 폴백하지 않고 있는 대로 가져온다. 종속기업이 없는 회사는
    연결을 제출하지 않으므로 한쪽만 돌아오는 것이 정상이다.

    Returns:
        {"CFS": [...], "OFS": [...]} — 없는 구분은 키 자체가 빠진다.
    """
    result: dict[str, list[dict]] = {}

    for fs_div in ("CFS", "OFS"):
        try:
            rows = fetch_financials(corp_code, bsns_year, fs_div, reprt_code)
            if rows:
                result[fs_div] = rows
        except DartError as e:
            if e.status != "013":       # 013 = 데이터 없음. 그 외는 진짜 오류다
                raise
            logger.info(
                f"{FS_DIV_LABELS[fs_div]}재무제표 없음 ({corp_code} {bsns_year})"
            )

    return result


# ── 응답 파싱 ──────────────────────────────────────────────────────

def parse_amount(value: Optional[str]) -> Optional[int]:
    """'9,999,999,999' → 9999999999. 빈 값·'-' 는 None."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "-"):
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            logger.debug(f"금액 파싱 실패: {value!r}")
            return None


def prior_amount(row: dict) -> Optional[int]:
    """전기 금액. 재무제표 구분과 보고서 종류에 따라 필드가 다르다.

    분기·반기의 손익계산서(IS/CIS)는 frmtrm_amount 가 비어 있고
    frmtrm_q_amount 에 값이 온다. 재무상태표(BS)는 분기에도
    frmtrm_amount 를 쓴다.
    """
    value = parse_amount(row.get("frmtrm_amount"))
    if value is None:
        value = parse_amount(row.get("frmtrm_q_amount"))
    return value


def current_amount(row: dict, cumulative: bool = True) -> Optional[int]:
    """당기 금액.

    분기 손익계산서의 thstrm_amount 는 3개월 금액이므로, 누적이 필요하면
    thstrm_add_amount 를 우선한다. 사업보고서에는 add 가 비어 있어
    자연히 thstrm_amount 로 떨어진다.
    """
    if cumulative:
        value = parse_amount(row.get("thstrm_add_amount"))
        if value is not None:
            return value
    return parse_amount(row.get("thstrm_amount"))


# ── 정기보고서 주요정보 (DS002) ────────────────────────────────────

# 이 API들은 날짜 범위가 아니라 (corp_code, bsns_year, reprt_code) 로 조회한다.
# 사업보고서에서 뽑아낸 표이므로, "어느 사업연도의 보고서인지"가 기준이 된다.
MAJOR_INFO_APIS = {
    "배당":        ("alotMatter.json",                "배당에 관한 사항"),
    "증자":        ("irdsSttus.json",                 "증자(감자) 현황"),
    "자기주식":     ("tesstkAcqsDspsSttus.json",       "자기주식 취득·처분 현황"),
    "타법인출자":   ("otrCprInvstmntSttus.json",       "타법인 출자현황"),
    "최대주주":     ("hyslrSttus.json",                "최대주주 현황"),
    "최대주주변동": ("hyslrChgSttus.json",             "최대주주 변동현황"),
    "감사의견":     ("accnutAdtorNmNdAdtOpinion.json", "회계감사인의 명칭 및 감사의견"),
    "감사용역":     ("adtServcCnclsSttus.json",        "감사용역 체결현황"),
}


def fetch_major_info(
    corp_code: str, bsns_year: int, api_file: str, reprt_code: str = REPRT_ANNUAL
) -> list[dict]:
    """정기보고서 주요정보 한 종류를 조회한다."""
    data = _get(
        api_file,
        corp_code=corp_code,
        bsns_year=str(bsns_year),
        reprt_code=reprt_code,
    )
    return data.get("list", [])


def target_business_years(today, back_years: int = 2) -> list[int]:
    """직전 회계연도 개시일부터 오늘까지 공시된 사업보고서의 사업연도들.

    사업보고서는 사업연도 종료 후 90일 이내에 제출되므로, 예를 들어
    2026-08-26 기준 창(2025-01-01 ~ 2026-08-26)에는 2025년 3월경 제출된
    2024 사업연도분과 2026년 3월경 제출된 2025 사업연도분이 들어온다.
    """
    latest = today.year - 1
    return list(range(latest - back_years + 1, latest + 1))


# ── 공시 목록 (DS001 list.json) ────────────────────────────────────

# pblntf_ty 코드. 감사 관련성이 높은 것만 기본값으로 쓴다.
PUBLIC_TYPES = {
    "A": "정기공시",
    "B": "주요사항보고",      # 자기주식취득결정·합병·유상증자 등 기중 이벤트
    "C": "발행공시",
    "D": "지분공시",          # 임원·주요주주 소유상황 — 건수가 많고 관련성은 낮다
    "E": "기타공시",
    "F": "외부감사관련",      # 감사보고서 제출, 감사인 선임·변경
    "I": "거래소공시",        # 수시공시·자율공시·공정공시
    "J": "공정위공시",        # 대규모내부거래 = 특수관계자 거래
}

DEFAULT_PUBLIC_TYPES = ("B", "F", "I", "J")

MAX_PAGE_COUNT = 100


def fetch_disclosure_list(
    corp_code: str,
    bgn_de: str,
    end_de: str,
    pblntf_ty: Optional[str] = None,
    max_pages: int = 20,
) -> list[dict]:
    """기간·유형별 공시 목록. 페이지를 끝까지 따라간다.

    bgn_de·end_de 는 YYYYMMDD. 주요정보(DS002)와 달리 이쪽은 날짜로 조회하므로
    "직전 회계연도 개시일 ~ 오늘" 창을 그대로 쓸 수 있다.
    """
    items: list[dict] = []

    for page in range(1, max_pages + 1):
        params = {
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_no": str(page),
            "page_count": str(MAX_PAGE_COUNT),
        }
        if pblntf_ty:
            params["pblntf_ty"] = pblntf_ty

        try:
            data = _get("list.json", **params)
        except DartError as e:
            if e.status == "013":       # 이 유형에 해당 기간 공시가 없다
                break
            raise

        rows = data.get("list", [])
        # 응답에는 pblntf_ty 가 없다. 요청한 유형을 알고 있으니 여기서 새긴다.
        for row in rows:
            row.setdefault("pblntf_ty", pblntf_ty or "")
        items.extend(rows)

        if page >= int(data.get("total_page", 1) or 1):
            break

    return items


# 보고서명 → 감사 시사점. 위에서부터 먼저 맞는 것을 쓴다.
# 보고서명이 정형화돼 있어 규칙만으로 충분하다 (AI 호출 불필요).
FILING_TAGS: list[tuple[str, tuple[str, ...]]] = [
    ("계속기업",   ("부도", "당좌거래정지", "영업정지", "회생절차", "파산",
                   "채권은행", "관리절차", "해산사유", "자본잠식")),
    ("사업결합",   ("합병", "분할", "영업양수", "영업양도", "주식교환", "주식이전",
                   "자산양수", "자산양도", "타법인주식")),
    ("특수관계자", ("대규모내부거래", "동일인등출자계열회사", "계열회사와의",
                   "특수관계인", "이해관계자와의")),
    ("외부감사",   ("감사보고서", "감사인", "회계처리기준", "재무제표재작성",
                   "외부감사", "감리")),
    # 증권발행제한·해임권고는 증선위가 과징금과 한 의결로 함께 내리는 조치다.
    # 이름에 '제재' 라는 말이 없어 규칙에 안 걸리고 미분류로 떨어졌다.
    ("소송·제재",  ("소송", "제재", "과징금", "벌금", "행정처분", "조사", "고발",
                   "증권발행제한", "발행제한", "해임권고", "직무정지", "영업정지처분")),
    ("자본거래",   ("자기주식", "유상증자", "무상증자", "감자", "전환사채",
                   "신주인수권부사채", "교환사채", "사채권", "주식매수선택권")),
    ("배당",       ("배당",)),
    ("정기보고서", ("사업보고서", "반기보고서", "분기보고서")),
]


def tag_filing(report_nm: str) -> Optional[str]:
    """보고서명에서 감사 시사점 태그를 뽑는다. 해당 없으면 None."""
    name = (report_nm or "").replace(" ", "")
    for tag, keywords in FILING_TAGS:
        if any(kw in name for kw in keywords):
            return tag
    return None


def fiscal_window(today) -> tuple[str, str]:
    """직전 회계연도 개시일 ~ 오늘. list.json 형식(YYYYMMDD)으로 돌려준다.

    2026년 기말감사라면 2025-01-01 ~ 오늘이 되어, 2025년 1역년 공시와
    2026년 기중 공시가 모두 들어온다.
    """
    from datetime import date as _date
    return _date(today.year - 1, 1, 1).strftime("%Y%m%d"), today.strftime("%Y%m%d")
