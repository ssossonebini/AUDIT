"""사업보고서 원문(document.xml) 수집·분할.

재무제표 API가 계정과 금액만 주는 데 반해 이쪽은 보고서 전문이라, 주석과
회사가 직접 기재한 내용이 들어온다. 특수관계자 거래·우발부채처럼 API 로는
잡히지 않던 것이 여기 있다.

실제 응답을 확인해 얻은 사실 (삼성전자 제57기 기준):

- ZIP 이지만 Content-Type 이 application/x-msdownload 로 온다.
  매직바이트 PK\\x03\\x04 로 판별해야 한다. 오류도 200 으로 오기 때문이다.
- 엔트리가 셋이다 — 본문(8.3MB) · 감사보고서(0.6MB) · 연결감사보고서(0.7MB).
  감사보고서에는 핵심감사사항 본문이 있어 주요정보의 한 줄 요약보다 깊다.
- 인코딩은 UTF-8.
- **엄밀한 XML 이 아니다.** 이스케이프되지 않은 & 가 972개(R&D 등),
  < 가 8개(`< TV 시장점유율 추이 >`) 있다. ElementTree 는 실패하므로
  lxml 의 recover=True 로 읽는다.
- 목차는 SECTION-1(14) → SECTION-2(43) 이고 제목은 각 섹션의 <TITLE> 이다.
- **주석은 SECTION-3 으로 내려가지 않는다.** 「3. 연결재무제표 주석」 하나의
  SECTION-2 안에 <TITLE> 34개가 평평하게 나열된다. 그래서 개별 주석을 뽑으려면
  SECTION 이 아니라 TITLE 위치로 잘라야 한다.
- 표는 TD 외에 TE(16,845) · TU(631) 를 쓴다. 함께 읽지 않으면 표가 빈다.
"""

import io
import logging
import re
import zipfile
from typing import Iterator, Optional

import requests
from lxml import etree

from app.crawler.dart_client import BASE_URL, DartError, _require_key

logger = logging.getLogger(__name__)

TIMEOUT = 120
ZIP_MAGIC = b"PK\x03\x04"

# 표 안에서 칸 노릇을 하는 태그. TE·TU 를 빼면 표 내용이 통째로 사라진다.
CELL_TAGS = {"TD", "TE", "TH", "TU"}

# 감사에서 먼저 볼 섹션·주석. 제목에 이 말이 들어가면 표시해 둔다.
AUDIT_KEYWORDS = (
    "주석", "재고자산", "충당부채", "우발부채", "약정사항", "법인세",
    "특수관계자", "사업결합", "부문별", "금융상품", "손상", "매출채권",
    "수익", "리스", "종속기업", "관계기업", "차입금", "사채",
    "대주주", "계열회사", "감사의견", "핵심감사사항", "경영진단",
    "소송", "제재", "우발상황",
)


def is_audit_relevant(title: str) -> bool:
    name = (title or "").replace(" ", "")
    return any(kw in name for kw in AUDIT_KEYWORDS)


# ── 내려받기 ───────────────────────────────────────────────────────

def fetch_document(rcept_no: str) -> dict[str, str]:
    """공시서류 원본을 받아 {파일명: XML 텍스트} 로 돌려준다."""
    resp = requests.get(
        f"{BASE_URL}/document.xml",
        params={"crtfc_key": _require_key(), "rcept_no": rcept_no},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()

    # 오류도 200 으로 오고 Content-Type 은 ZIP 일 때도 x-msdownload 다.
    # 매직바이트로 판별하는 것이 유일하게 확실하다.
    if not resp.content.startswith(ZIP_MAGIC):
        status = re.search(rb"<status>(\d+)</status>", resp.content)
        raise DartError(status.group(1).decode() if status else "900")

    documents: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xml"):
                continue
            documents[name] = zf.read(name).decode("utf-8", errors="replace")

    logger.info(f"원문 {len(documents)}개 파일 수신 ({rcept_no})")
    return documents


def document_label(filename: str) -> str:
    """엔트리 이름으로 문서 종류를 가늠한다.

    본문은 {접수번호}.xml, 첨부는 {접수번호}_00760.xml 처럼 접미사가 붙는다.
    """
    stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return "본문" if "_" not in stem else f"첨부({stem.split('_')[-1]})"


# ── 파싱 ───────────────────────────────────────────────────────────

def _root(xml_text: str):
    """이스케이프가 깨진 문서라 recover 로 읽는다."""
    parser = etree.XMLParser(recover=True, huge_tree=True)
    return etree.fromstring(xml_text.encode("utf-8"), parser=parser)


def _text_of(node) -> str:
    """표를 보존하며 텍스트를 뽑는다."""
    if node.tag == "TABLE":
        rows = []
        for tr in node.iter("TR"):
            cells = [
                " ".join(c.itertext()).strip()
                for c in tr
                if c.tag in CELL_TAGS
            ]
            if any(cells):
                rows.append(" | ".join(cells))
        return "\n".join(rows)

    return " ".join(t.strip() for t in node.itertext() if t.strip())


def _title_text(node) -> str:
    return re.sub(r"\s+", " ", " ".join(node.itertext())).strip()


def _body_until_next_title(title_node) -> str:
    """평평하게 나열된 TITLE 사이의 본문을 모은다.

    주석이 이 구조다 — SECTION 으로 감싸이지 않고 TITLE 이 형제로 늘어선다.
    """
    parts = []
    for sibling in title_node.itersiblings():
        if sibling.tag == "TITLE":
            break
        text = _text_of(sibling)
        if text:
            parts.append(text)
    return "\n".join(parts)


def parse_sections(xml_text: str) -> list[dict]:
    """목차 단위로 쪼갠다.

    SECTION-1 / SECTION-2 는 섹션 태그로, 그 안에 평평하게 놓인 TITLE 은
    하위 항목(주석 등)으로 잡는다.

    Returns:
        [{level, title, parent, section_no, body, chars, audit_relevant}]
    """
    root = _root(xml_text)
    if root is None:
        logger.warning("원문을 파싱하지 못했습니다")
        return []

    sections: list[dict] = []

    def _emit(level: int, title: str, parent: str, node, body: str) -> None:
        if not title:
            return
        sections.append({
            "level": level,
            "title": title,
            "parent": parent,
            "section_no": node.get("AASSOCNOTE") or node.get("ATOCID") or "",
            "body": body,
            "chars": len(body),
            "audit_relevant": is_audit_relevant(title),
        })

    for s1 in root.iter("SECTION-1"):
        t1 = s1.find("TITLE")
        if t1 is None:
            continue
        name1 = _title_text(t1)

        children = list(s1.iter("SECTION-2"))
        if not children:
            _emit(1, name1, "", t1, _text_of(s1))
            continue

        _emit(1, name1, "", t1, "")     # 대분류는 목차 노릇만 한다

        for s2 in children:
            t2 = s2.find("TITLE")
            if t2 is None:
                continue
            name2 = _title_text(t2)

            # SECTION-2 의 직계 TITLE 중 첫 번째를 뺀 나머지가 하위 항목이다
            flat = [t for t in s2.findall("TITLE") if t is not t2]

            if not flat:
                _emit(2, name2, name1, t2, _text_of(s2))
                continue

            _emit(2, name2, name1, t2, _body_until_next_title(t2))
            for t3 in flat:
                _emit(3, _title_text(t3), name2, t3, _body_until_next_title(t3))

    return sections
