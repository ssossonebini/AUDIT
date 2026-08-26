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
- **꺾쇠로 감싼 한글 표기는 recover 로 못 고친다.** 영풍 제75기에는
  `<당기말>` · `<전기>` 같은 표기가 24곳 있는데, 한글은 XML 이름으로
  유효해서 lxml 이 이것을 **여는 태그로 인식한다.** 닫는 태그가 없으니
  뒤따르는 요소가 전부 그 안으로 끌려 들어가 SECTION-1 11개가 서로
  중첩됐고, 구간 수가 43 → 124 로 부풀었다. 삼성전자가 무사했던 것은
  그 문서의 꺾쇠 표기가 `< TV ... >` 처럼 공백을 품어 lxml 이 버렸기
  때문일 뿐이다. 파싱 전에 escape_stray_markup() 으로 태그가 아닌 `<` 를
  &lt; 로 바꾼다.
- 목차는 SECTION-1(14) → SECTION-2(43) 이고 제목은 각 섹션의 <TITLE> 이다.
- **주석은 SECTION-3 으로 내려가지 않는다.** 「3. 연결재무제표 주석」 SECTION-2
  아래에 TABLE-GROUP 34개가 놓이고, 각 TABLE-GROUP 이 TITLE 을 하나씩 갖는다.
  문서 전체 TITLE 143개의 부모는 TABLE-GROUP 83 / SECTION-2 43 / SECTION-1 14 라,
  SECTION 의 직계 TITLE 만 보면 주석이 통째로 뭉친다.
- 표는 TD 외에 TE(16,845) · TU(631) 를 쓴다. 함께 읽지 않으면 표가 빈다.
  TABLE 2,071개 중 SECTION 직계는 314개뿐이고 나머지는 TABLE-GROUP·LIBRARY·TD
  안쪽에 있으므로, 텍스트 추출은 재귀로 내려가야 표가 살아남는다.
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
# 중점심사 이슈에 대응하는 주석이 빠지지 않도록 계정 이름을 폭넓게 담는다 —
# 투자부동산처럼 하나가 빠지면 그 해 중점심사 항목을 통째로 놓친다.
AUDIT_KEYWORDS = (
    # 자산
    "재고자산", "매출채권", "유형자산", "무형자산", "개발비", "투자부동산",
    "사용권자산", "리스", "손상", "영업권",
    # 부채·자본
    "충당부채", "우발부채", "우발상황", "약정사항", "차입금", "사채",
    "퇴직급여", "주식기준보상", "자기주식",
    # 손익
    "수익", "법인세", "이연법인세", "정부보조금", "건설계약", "외화",
    # 금융상품·공정가치
    "금융상품", "공정가치", "파생상품", "위험관리",
    # 관계·구조
    "특수관계자", "종속기업", "관계기업", "공동기업", "사업결합", "부문별",
    "대주주", "계열회사", "비지배지분",
    # 보고서 섹션
    "주석", "감사의견", "핵심감사사항", "경영진단", "소송", "제재", "계속기업",
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
            documents[name] = decode_xml(zf.read(name), name)

    logger.info(f"원문 {len(documents)}개 파일 수신 ({rcept_no})")
    return documents


def decode_xml(raw: bytes, name: str = "") -> str:
    """UTF-8 을 먼저 보고, 아니면 CP949 로 읽는다.

    최근 보고서는 UTF-8 이지만 구형 문서에는 EUC-KR 이 있다. 처음부터
    errors="replace" 로 열면 그런 문서가 깨진 글자로 조용히 저장된다 —
    실패보다 나쁘다. 판독 자체가 안 되는 경우에만 마지막 수단으로 쓴다.
    """
    for encoding in ("utf-8", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    logger.warning(f"인코딩을 판별하지 못해 일부 글자가 깨질 수 있습니다: {name}")
    return raw.decode("utf-8", errors="replace")


def document_label(filename: str) -> str:
    """엔트리 이름으로 문서 종류를 가늠한다.

    본문은 {접수번호}.xml, 첨부는 {접수번호}_00760.xml 처럼 접미사가 붙는다.
    """
    stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return "본문" if "_" not in stem else f"첨부({stem.split('_')[-1]})"


# ── 파싱 ───────────────────────────────────────────────────────────

# 태그로 볼 수 있는 것만 추린다. 이름은 ASCII 로 시작해야 하고, 속성은
# `이름=값` 꼴이어야 한다. 이 둘을 요구해야 <당기말> 도, < TV 점유율 > 도
# 태그로 오인되지 않는다.
_NAME = r"[A-Za-z_:][A-Za-z0-9_.:-]*"
_ATTRS = rf"""(?:\s+{_NAME}\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'<>]+))*\s*"""
_MARKUP = re.compile(
    "<(?:"
    r"!\[CDATA\[.*?\]\]>"          # CDATA
    r"|!--.*?-->"                  # 주석
    r"|![^>]*>"                    # DOCTYPE 등
    r"|\?.*?\?>"                   # 처리 명령
    rf"|/{_NAME}\s*>"              # 닫는 태그
    rf"|{_NAME}{_ATTRS}/?>"        # 여는 태그
    ")|<",                         # 그 밖의 < 는 본문 글자다
    re.S,
)


def escape_stray_markup(xml_text: str) -> str:
    """태그가 아닌 `<` 를 &lt; 로 바꾼다.

    한글은 XML 이름으로 유효하다. 그래서 회사가 표 머리에 흔히 쓰는
    `<당기말>` 같은 표기를 lxml 이 여는 태그로 읽고, 닫는 태그가 없으니
    recover 모드가 뒤따르는 요소를 전부 그 안으로 밀어 넣는다. 구조가
    통째로 어긋나므로 파싱 전에 미리 손봐야 한다.

    `>` 는 그대로 둔다 — XML 본문에서 이스케이프 없이도 적법하다.
    """
    return _MARKUP.sub(lambda m: m.group(0) if len(m.group(0)) > 1 else "&lt;",
                       xml_text)


def _root(xml_text: str):
    """이스케이프가 깨진 문서라 recover 로 읽는다."""
    parser = etree.XMLParser(recover=True, huge_tree=True)
    return etree.fromstring(escape_stray_markup(xml_text).encode("utf-8"),
                            parser=parser)


def _render_table(table) -> str:
    """표를 행 단위로 편다. TE·TU 를 빼면 금액이 통째로 사라진다."""
    rows = []
    for tr in table.iter("TR"):
        cells = [
            re.sub(r"\s+", " ", " ".join(c.itertext())).strip()
            for c in tr
            if c.tag in CELL_TAGS
        ]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _text_of(node, skip=None) -> str:
    """표 구조를 보존하며 텍스트를 뽑는다.

    itertext() 로 납작하게 펴면 표가 뭉개진다. TABLE 은 대부분 TABLE-GROUP 이나
    LIBRARY 안쪽에 있어, 직계만 보는 방식으로는 걸리지 않는다. 그래서 재귀로
    내려가며 TABLE 을 만나는 즉시 행 단위로 렌더링한다.
    """
    if node.tag == "TABLE":
        return _render_table(node)

    parts = []
    if node.text and node.text.strip():
        parts.append(node.text.strip())

    for child in node:
        if child.tag == "TITLE" or child is skip:
            pass
        else:
            rendered = _text_of(child)
            if rendered:
                parts.append(rendered)
        if child.tail and child.tail.strip():
            parts.append(child.tail.strip())

    return "\n".join(parts)


def _title_text(node) -> str:
    return re.sub(r"\s+", " ", " ".join(node.itertext())).strip()


def _body_until_next_title(title_node) -> str:
    """다음 하위 항목이 시작되기 전까지의 본문을 모은다.

    중단 조건이 둘이다. TITLE 이 형제로 놓인 판본에서는 그 TITLE 에서 멈추고,
    TABLE-GROUP 에 감싸인 보통의 경우에는 **TITLE 을 품은 컨테이너**에서 멈춘다.
    후자를 빠뜨리면 중분류가 하위 주석 본문을 전부 삼킨다.
    """
    parts = []
    for sibling in title_node.itersiblings():
        if sibling.tag == "TITLE" or sibling.find("TITLE") is not None:
            break
        text = _text_of(sibling)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _sub_items(section, own_title) -> list[tuple]:
    """SECTION-2 안의 하위 항목(주석 등)을 (TITLE, 본문) 으로 뽑는다.

    실제 문서에서 주석은 SECTION-2 의 직계 TITLE 이 아니라 TABLE-GROUP 안에
    하나씩 들어 있다 (TITLE 143개의 부모: TABLE-GROUP 83 / SECTION-2 43).
    직계만 찾으면 주석 34개가 통째로 뭉친다.

    판본 차이를 감안해 두 배치를 모두 받는다 — TABLE-GROUP 에 감싸인 것과
    형제로 늘어선 것.
    """
    items = []
    for child in section:
        if child is own_title:
            continue

        if child.tag == "TITLE":                       # 형제로 놓인 경우
            items.append((child, _body_until_next_title(child)))
            continue

        inner = child.find("TITLE")                    # TABLE-GROUP 등에 감싸인 경우
        if inner is not None:
            items.append((inner, _text_of(child, skip=inner)))

    return items


def _owned(section, tag: str) -> list:
    """자기 몫의 하위 섹션만 고른다.

    iter() 는 자손을 전부 훑으므로, 어떤 이유로든 SECTION-1 이 서로 중첩되면
    바깥 섹션이 안쪽 섹션의 SECTION-2 까지 자기 것으로 다시 내놓는다. 가장
    가까운 SECTION-1 조상이 자신인 것만 남겨 중복을 막는다.
    """
    return [
        node for node in section.iter(tag)
        if next((a for a in node.iterancestors() if a.tag == section.tag), None)
        is section
    ]


def parse_sections(xml_text: str) -> list[dict]:
    """목차 단위로 쪼갠다.

    SECTION-1 / SECTION-2 는 섹션 태그이고, 하위 항목(주석 등)은 SECTION-2 안의
    TABLE-GROUP 에 하나씩 들어 있다. _sub_items() 참조.

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

        children = _owned(s1, "SECTION-2")
        if not children:
            _emit(1, name1, "", t1, _text_of(s1))
            continue

        _emit(1, name1, "", t1, "")     # 대분류는 목차 노릇만 한다

        for s2 in children:
            t2 = s2.find("TITLE")
            if t2 is None:
                continue
            name2 = _title_text(t2)

            items = _sub_items(s2, t2)

            if not items:
                _emit(2, name2, name1, t2, _text_of(s2))
                continue

            # 하위 항목이 있으면 중분류는 머리말만 갖는다
            _emit(2, name2, name1, t2, _body_until_next_title(t2))
            for t3, body in items:
                _emit(3, _title_text(t3), name2, t3, body)

    return sections
