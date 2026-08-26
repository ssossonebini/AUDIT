"""사업보고서 원문(document.xml) 파싱 검증.

픽스처는 실제 응답 구조를 그대로 재현한다 (삼성전자 제57기):
- 이스케이프되지 않은 & 와 < 가 섞여 있어 엄밀한 XML 이 아니다
- **주석은 SECTION-2 의 직계 TITLE 이 아니라 TABLE-GROUP 안에** 하나씩 있다
  (TITLE 143개의 부모: TABLE-GROUP 83 / SECTION-2 43 / SECTION-1 14)
- **TABLE 은 SECTION 직계가 아니라 TABLE-GROUP·LIBRARY 안쪽**에 있다
  (2,071개 중 직계는 314개뿐) — 추출이 재귀가 아니면 표가 납작해진다
- 표는 TD 외에 TE·TU 를 쓴다

앞선 픽스처는 TITLE 을 SECTION-2 직계에 두어 이 두 경로를 짚지 못했고,
테스트 15개가 통과하는 동안 실제 문서에서는 주석이 하나도 분리되지 않았다.
"""

import io
import zipfile

import pytest

from app.crawler import dart_document as dd

# 실제 문서의 골격. R&D 의 & 와 '< TV 시장점유율 >' 의 < 를 일부러 넣었다.
XML = """<?xml version="1.0" encoding="utf-8"?>
<DOCUMENT>
<DOCUMENT-NAME ACODE="11011">사업보고서</DOCUMENT-NAME>
<COMPANY-NAME AREGCIK="00126380">삼성전자주식회사</COMPANY-NAME>
<BODY ATOCID="644">
  <SECTION-1 ACLASS="MANDATORY">
    <TITLE ATOC="Y" AASSOCNOTE="D-0-2-0-0" ENG="II. Business">II. 사업의 내용</TITLE>
    <SECTION-2>
      <TITLE ATOC="Y" AASSOCNOTE="D-0-2-1-0">1. 사업의 개요</TITLE>
      <P>R&D 투자를 확대하고 있습니다.</P>
      <P>< TV 시장점유율 추이 ></P>
    </SECTION-2>
  </SECTION-1>
  <SECTION-1 ACLASS="MANDATORY">
    <TITLE ATOC="Y" AASSOCNOTE="D-0-3-0-0">III. 재무에 관한 사항</TITLE>
    <SECTION-2>
      <TITLE ATOC="Y" AASSOCNOTE="D-0-3-3-0">3. 연결재무제표 주석</TITLE>
      <P>주석 머리말입니다.</P>
      <TABLE-GROUP>
        <TITLE ATOCID="579">8. 재고자산 (연결)</TITLE>
        <P>재고자산 평가충당금 내역입니다.</P>
        <TABLE>
          <TR><TH>구분</TH><TH>당기</TH></TR>
          <TR><TD>제품</TD><TE>1,000</TE></TR>
          <TR><TD>원재료</TD><TU>2,000</TU></TR>
        </TABLE>
      </TABLE-GROUP>
      <TABLE-GROUP>
        <TITLE ATOCID="602">31. 특수관계자와의 거래 (연결)</TITLE>
        <LIBRARY>
          <TABLE>
            <TR><TH>구분</TH><TH>삼성에스디에스㈜</TH></TR>
            <TR><TD>매출 등</TD><TE>110,512</TE></TR>
          </TABLE>
        </LIBRARY>
      </TABLE-GROUP>
      <TABLE-GROUP>
        <TITLE ATOCID="605">32. 비지배지분 (연결)</TITLE>
        <P>비지배지분 내역입니다.</P>
      </TABLE-GROUP>
    </SECTION-2>
  </SECTION-1>
</BODY>
</DOCUMENT>
"""


@pytest.fixture
def sections():
    return dd.parse_sections(XML)


def _by_title(sections, needle):
    return next(s for s in sections if needle in s["title"])


# ── 깨진 XML ───────────────────────────────────────────────────────

def test_unescaped_characters_do_not_break_parsing():
    """R&D 의 & 와 '< TV …' 의 < 때문에 ElementTree 는 실패한다."""
    import xml.etree.ElementTree as ET

    with pytest.raises(ET.ParseError):
        ET.fromstring(XML)

    assert dd.parse_sections(XML), "recover 파서로는 읽혀야 한다"


def test_parser_returns_empty_rather_than_raising_on_garbage():
    assert dd.parse_sections("완전히 XML 이 아닌 문자열") == []


# ── 목차 구조 ──────────────────────────────────────────────────────

def test_top_level_sections_are_captured(sections):
    level1 = [s["title"] for s in sections if s["level"] == 1]
    assert "II. 사업의 내용" in level1
    assert "III. 재무에 관한 사항" in level1


def test_second_level_records_its_parent(sections):
    notes = _by_title(sections, "연결재무제표 주석")
    assert notes["level"] == 2
    assert notes["parent"] == "III. 재무에 관한 사항"


def test_notes_wrapped_in_table_groups_become_their_own_entries(sections):
    """주석은 SECTION-2 의 직계 TITLE 이 아니라 TABLE-GROUP 안에 있다.

    직계만 찾으면 34개가 통째로 뭉쳐 특수관계자 주석을 따로 꺼낼 수 없다.
    """
    titles = [s["title"] for s in sections if s["level"] == 3]

    assert "8. 재고자산 (연결)" in titles
    assert "31. 특수관계자와의 거래 (연결)" in titles
    assert "32. 비지배지분 (연결)" in titles


def test_a_note_body_does_not_bleed_into_its_neighbours(sections):
    """구간이 앞뒤 주석까지 넘어가면 안 된다."""
    related = _by_title(sections, "특수관계자")

    assert "삼성에스디에스" in related["body"]
    assert "비지배지분 내역" not in related["body"]
    assert "재고자산 평가충당금" not in related["body"]


def test_a_note_body_excludes_its_own_title(sections):
    related = _by_title(sections, "특수관계자")
    assert "31. 특수관계자와의 거래" not in related["body"]


def test_nested_tables_keep_their_rows(sections):
    """TABLE 은 대부분 TABLE-GROUP·LIBRARY 안쪽에 있다. 재귀가 아니면 납작해진다."""
    related = _by_title(sections, "특수관계자")

    assert "매출 등 | 110,512" in related["body"], "중첩 TABLE 이 뭉개졌습니다"


def test_section_headnote_is_kept_separate_from_the_notes(sections):
    """중분류에는 머리말만 남고 주석 본문이 섞이지 않아야 한다."""
    heading = _by_title(sections, "연결재무제표 주석")

    assert "주석 머리말" in heading["body"]
    assert "삼성에스디에스" not in heading["body"]


def test_section_number_is_kept_for_navigation(sections):
    assert _by_title(sections, "연결재무제표 주석")["section_no"] == "D-0-3-3-0"


# ── 표 ─────────────────────────────────────────────────────────────

def test_table_cells_in_te_and_tu_are_not_lost(sections):
    """TE·TU 를 빼면 금액이 통째로 사라진다 — TD 다음으로 흔한 칸 태그다."""
    inventory = _by_title(sections, "재고자산")

    assert "1,000" in inventory["body"], "TE 칸이 빠졌습니다"
    assert "2,000" in inventory["body"], "TU 칸이 빠졌습니다"
    assert "제품" in inventory["body"]


def test_table_rows_stay_on_separate_lines(sections):
    body = _by_title(sections, "재고자산")["body"]
    assert "제품 | 1,000" in body


# ── 감사 관련 표시 ─────────────────────────────────────────────────

def test_audit_relevant_titles_are_flagged(sections):
    assert _by_title(sections, "특수관계자")["audit_relevant"] is True
    assert _by_title(sections, "재고자산")["audit_relevant"] is True


def test_unrelated_sections_are_not_flagged(sections):
    assert _by_title(sections, "사업의 개요")["audit_relevant"] is False


def test_keyword_matching_ignores_spacing():
    assert dd.is_audit_relevant("16. 우발부채와 약정사항 (연결)") is True
    assert dd.is_audit_relevant("VII. 주주에 관한 사항") is False


# ── ZIP 처리 ───────────────────────────────────────────────────────

def test_document_label_separates_body_from_attachments():
    assert dd.document_label("20260310002820.xml") == "본문"
    assert dd.document_label("20260310002820_00760.xml") == "첨부(00760)"


def test_a_non_zip_response_is_reported_as_a_dart_error(monkeypatch):
    """오류도 HTTP 200 으로 오고 Content-Type 은 ZIP 일 때도 x-msdownload 다."""
    class _Resp:
        content = b'<result><status>020</status></result>'
        def raise_for_status(self): pass

    monkeypatch.setattr(dd.requests, "get", lambda *a, **k: _Resp())
    monkeypatch.setattr(dd, "_require_key", lambda: "key")

    with pytest.raises(dd.DartError) as exc:
        dd.fetch_document("20260310002820")
    assert exc.value.status == "020"


def test_every_xml_entry_in_the_zip_is_returned(monkeypatch):
    """본문 외에 감사보고서·연결감사보고서가 첨부로 함께 온다."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("20260310002820.xml", XML)
        zf.writestr("20260310002820_00760.xml", XML)
        zf.writestr("20260310002820_00761.xml", XML)

    class _Resp:
        content = buffer.getvalue()
        def raise_for_status(self): pass

    monkeypatch.setattr(dd.requests, "get", lambda *a, **k: _Resp())
    monkeypatch.setattr(dd, "_require_key", lambda: "key")

    documents = dd.fetch_document("20260310002820")
    assert len(documents) == 3
    assert {dd.document_label(n) for n in documents} == {
        "본문", "첨부(00760)", "첨부(00761)",
    }


def test_keywords_cover_the_accounts_that_focus_areas_target():
    """중점심사 이슈에 대응하는 주석이 표시에서 빠지면 그 항목을 통째로 놓친다.

    투자부동산이 실제로 빠져 있었고, 2026년 중점심사 이슈 중 하나였다.
    """
    for account in (
        "투자부동산", "유형자산", "무형자산", "개발비", "영업권",
        "퇴직급여", "파생상품", "공정가치", "주식기준보상",
        "정부보조금", "건설계약", "이연법인세", "계속기업",
    ):
        assert dd.is_audit_relevant(account), f"{account} 가 감사 관련에서 빠졌습니다"


def test_keywords_still_exclude_administrative_sections():
    for section in ("VII. 주주에 관한 사항", "VIII. 임원 및 직원 등에 관한 사항",
                    "전문가의 확인"):
        assert dd.is_audit_relevant(section) is False, f"{section} 이 잘못 표시됐습니다"


# ── 인코딩 ─────────────────────────────────────────────────────────

def test_utf8_documents_decode_cleanly():
    assert dd.decode_xml("주석 본문".encode("utf-8")) == "주석 본문"


def test_legacy_cp949_documents_are_not_silently_mangled():
    """구형 보고서에 EUC-KR 이 있다. replace 로 먼저 열면 조용히 깨진다."""
    raw = "특수관계자와의 거래".encode("cp949")

    assert dd.decode_xml(raw) == "특수관계자와의 거래"
    assert "�" not in dd.decode_xml(raw), "대체문자가 섞였습니다"


def test_undecodable_bytes_fall_back_rather_than_raising():
    assert dd.decode_xml(b"\xff\xfe\x00\x01") is not None


# ── 꺾쇠로 감싼 한글 표기 (영풍 제75기) ─────────────────────────────

# 회사가 표 머리에 흔히 쓰는 <당기말> 표기. 한글은 XML 이름으로 유효해서
# lxml 이 여는 태그로 읽고, 닫는 태그가 없어 뒤따르는 요소를 전부 삼킨다.
YP_XML = """<?xml version="1.0" encoding="utf-8"?>
<DOCUMENT>
<BODY>
  <SECTION-1>
    <TITLE>III. 재무에 관한 사항</TITLE>
    <SECTION-2>
      <TITLE>3. 연결재무제표 주석</TITLE>
      <P><당기말></P>
      <TABLE-GROUP>
        <TITLE>16. 유형자산</TITLE>
        <P>손상차손 135,800 백만원을 인식하였습니다.</P>
      </TABLE-GROUP>
    </SECTION-2>
  </SECTION-1>
  <SECTION-1>
    <TITLE>V. 회계감사인의 감사의견 등</TITLE>
    <SECTION-2>
      <TITLE>3. 제재 등과 관련된 사항</TITLE>
      <P><전기></P>
      <P>해당사항 없음</P>
    </SECTION-2>
  </SECTION-1>
</BODY>
</DOCUMENT>
"""


def test_angle_wrapped_korean_label_is_not_read_as_a_tag():
    """<당기말> 이 태그로 읽히면 이후 요소가 전부 그 안으로 끌려 들어간다."""
    root = dd._root(YP_XML)
    assert root.find(".//당기말") is None, "한글 표기가 태그로 파싱됐습니다"


def test_angle_wrapped_label_does_not_nest_the_following_sections():
    root = dd._root(YP_XML)
    for s1 in root.iter("SECTION-1"):
        assert not any(a.tag == "SECTION-1" for a in s1.iterancestors()), \
            "SECTION-1 이 서로 중첩됐습니다"


def test_sections_are_not_duplicated_by_the_stray_angle_bracket():
    """구간 수가 부풀지 않아야 한다 — 영풍은 43 → 124 로 늘었다."""
    got = dd.parse_sections(YP_XML)
    titles = [s["title"] for s in got]
    assert len(titles) == len(set(titles)), f"중복된 구간: {titles}"


def test_the_label_survives_as_body_text():
    """태그로 오인하지 않되 글자는 버리지 않는다."""
    got = dd.parse_sections(YP_XML)
    joined = "\n".join(s["body"] for s in got)
    assert "<당기말>" in joined


def test_content_after_the_label_is_still_reachable():
    got = dd.parse_sections(YP_XML)
    유형자산 = _by_title(got, "유형자산")
    assert "135,800" in 유형자산["body"]
    assert 유형자산["parent"] == "3. 연결재무제표 주석"


def test_real_tags_are_left_alone():
    text = '<TABLE-GROUP ACLASS="NORMAL"><TD/></TABLE-GROUP><!-- 주석 -->'
    assert dd.escape_stray_markup(text) == text


def test_a_bare_less_than_in_body_text_is_escaped():
    assert dd.escape_stray_markup("<P>a < b</P>") == "<P>a &lt; b</P>"


def test_a_spaced_pseudo_tag_is_kept_as_text():
    """< TV 시장점유율 추이 > 는 속성 꼴이 아니므로 태그가 아니다."""
    assert dd.escape_stray_markup("< TV 추이 >") == "&lt; TV 추이 >"


# ── 첨부 문서 이름 ─────────────────────────────────────────────────

def test_attachment_is_named_from_the_document_itself():
    """'첨부(00760)' 으로는 무엇인지 알 수 없다. 문서가 제 이름을 갖고 있다."""
    xml = '<DOCUMENT><DOCUMENT-NAME ACODE="11011">감사보고서</DOCUMENT-NAME></DOCUMENT>'
    assert dd.document_label("20260317000753_00760.xml", xml) == "감사보고서"


def test_label_falls_back_to_the_entry_number():
    assert dd.document_label("20260317000753_00760.xml") == "첨부(00760)"
    assert dd.document_label("20260317000753.xml") == "본문"


def test_documents_that_share_a_name_stay_apart():
    """이름이 겹치면 두 문서의 구간이 한 탭에 섞인다."""
    same = "<DOCUMENT><DOCUMENT-NAME>감사보고서</DOCUMENT-NAME></DOCUMENT>"
    labels = dd.document_labels({
        "20260317000753.xml": "<DOCUMENT><DOCUMENT-NAME>사업보고서</DOCUMENT-NAME></DOCUMENT>",
        "20260317000753_00760.xml": same,
        "20260317000753_00761.xml": same,
    })
    assert labels["20260317000753.xml"] == "사업보고서"
    assert len(set(labels.values())) == 3, f"이름이 겹쳤습니다: {labels}"
    assert "00761" in labels["20260317000753_00761.xml"]
