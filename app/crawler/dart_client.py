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


def fetch_financials_with_fallback(
    corp_code: str, bsns_year: int, reprt_code: str = REPRT_ANNUAL
) -> tuple[str, list[dict]]:
    """연결(CFS)을 먼저 시도하고, 없으면 개별(OFS)로 내려간다.

    종속기업이 없는 회사는 연결재무제표를 제출하지 않는다.

    Returns:
        (실제로 받아온 fs_div, 행 목록)
    """
    try:
        rows = fetch_financials(corp_code, bsns_year, "CFS", reprt_code)
        if rows:
            return "CFS", rows
    except DartError as e:
        if e.status != "013":       # 013 = 데이터 없음 → 개별로 재시도
            raise
        logger.info(f"연결재무제표 없음 ({corp_code} {bsns_year}) — 개별로 시도")

    return "OFS", fetch_financials(corp_code, bsns_year, "OFS", reprt_code)


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
