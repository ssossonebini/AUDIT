"""기준서 PDF 분할 로직 검증.

PDF 렌더링 없이 텍스트 단계만 검사한다. 실제 기준서 PDF는 기준서명이
머리말로 매 페이지 반복되므로, 그것을 절 시작으로 오인하면 파일이
수백 개로 쪼개진다.
"""

import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "build_skill_refs",
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "build_skill_refs.py",
)
bsr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bsr)


def _body(tag: str, n: int = 60) -> str:
    return "\n".join(f"{tag} 문단 {i}. 본문 내용이 이어집니다." for i in range(n))


def test_kifrs_headings_are_detected():
    text = (
        "기준서 제1115호 고객과의 계약에서 생기는 수익\n" + _body("1115") + "\n"
        "기준서 제1116호 리스\n" + _body("1116") + "\n"
        "기업회계기준서 제1109호 금융상품\n" + _body("1109")
    )
    found = bsr.find_sections(text, bsr.PATTERNS["kifrs"])

    assert [n for _, n, _ in found] == ["1115", "1116", "1109"]
    assert found[0][2].startswith("고객과의 계약")
    assert found[1][2] == "리스"


def test_audit_standard_headings_are_detected():
    text = (
        "감사기준서 200 재무제표 감사의 전반적인 목적\n" + _body("200") + "\n"
        "감사기준서 315 왜곡표시 위험의 식별과 평가\n" + _body("315")
    )
    found = bsr.find_sections(text, bsr.PATTERNS["audit"])
    assert [n for _, n, _ in found] == ["200", "315"]


def test_repeated_running_head_does_not_split_the_file():
    """기준서명이 매 페이지 머리말로 반복돼도 절은 하나여야 한다."""
    page = "기준서 제1115호 수익\n" + _body("1115", 8)
    text = "\n".join([page] * 5)          # 5페이지에 걸쳐 반복

    found = bsr.find_sections(text, bsr.PATTERNS["kifrs"])
    assert len(found) == 1, f"머리말 반복을 절 시작으로 오인했습니다 ({len(found)}개)"


def test_strip_running_heads_removes_repeated_lines():
    pages = [
        f"한국회계기준원\n본문 {i} 줄입니다.\n- {i} -"
        for i in range(10)
    ]
    cleaned = bsr.strip_running_heads(pages)

    joined = "\n".join(cleaned)
    assert "한국회계기준원" not in joined, "반복 머리말이 남았습니다"
    assert "본문 3 줄입니다." in joined, "본문까지 지우면 안 됩니다"


def test_strip_running_heads_keeps_short_documents_intact():
    pages = ["표지", "본문"]
    assert bsr.strip_running_heads(pages) == pages


def test_slugify_builds_safe_filenames():
    name = bsr.slugify("1115", "고객과의 계약에서 생기는 수익", "kifrs")
    assert name.startswith("kifrs_1115_")
    assert name.endswith(".md")
    assert "/" not in name and " " not in name


# ── --mode file: PDF 하나가 기준서 하나인 경우 ────────────────────

def test_parse_filename_extracts_number_and_title():
    num, title = bsr.parse_filename(
        "시행중_K-IFRS_제1115호_고객과의_계약에서_생기는_수익"
        "(2018_개정_2021_타기준서_제정_수정목록_23-1_2020_구성양식_변경_반영)",
        "kifrs",
    )
    assert num == "1115"
    assert title == "고객과의 계약에서 생기는 수익"


def test_parse_filename_drops_revision_parenthetical():
    """괄호 안 개정 이력이 제목에 섞이면 파일명이 지저분해진다."""
    _, title = bsr.parse_filename(
        "시행중_K-IFRS_제1002호_재고자산(2007_제정_2017_타기준서_제정_수정목록_23-1)",
        "kifrs",
    )
    assert title == "재고자산"
    assert "2007" not in title


def test_parse_filename_handles_documents_without_a_number():
    """개념체계·실무서는 번호가 없다. 접두사만 걷어내고 제목을 남긴다."""
    num, title = bsr.parse_filename(
        "시행중_K-IFRS_재무보고를_위한_개념체계(2018_개정_2019_타기준서_개정)",
        "kifrs",
    )
    assert num == ""
    assert title == "재무보고를 위한 개념체계"


def test_parse_filename_for_audit_standards():
    num, title = bsr.parse_filename("감사기준서_제315호_위험평가(2023_개정)", "audit")
    assert num == "315"
    assert title == "위험평가"


def test_running_head_on_every_page_yields_one_section():
    """전문 PDF 는 페이지마다 기준서명이 반복된다. 절은 여전히 하나여야 한다.

    페이지가 MIN_SECTION_CHARS 보다 길어도 마찬가지다 — 실제 회계감사기준 전문에서
    이 때문에 39개 기준서가 496개 조각으로 쪼개지고 서로 덮어썼다.
    """
    page = "감사기준서 315 중요왜곡표시위험의 식별과 평가 목차\n" + _body("315", 60)
    text = "\n".join([page] * 20)

    found = bsr.find_sections(text, bsr.PATTERNS["audit"])
    assert [n for _, n, _ in found] == ["315"]


def test_table_of_contents_entry_does_not_win_over_the_body():
    """목차에 한 번 나온 번호가 본문 구간을 밀어내면 안 된다."""
    text = (
        "감사기준서 580 서면진술 ..... 500\n"        # 목차 줄
        + _body("머리", 40) + "\n"
        + "\n".join(
            ["감사기준서 580 서면진술 목차\n" + _body("580", 40)] * 6
        )
    )
    found = bsr.find_sections(text, bsr.PATTERNS["audit"])

    assert len(found) == 1
    start = found[0][0]
    assert "머리" not in text[start:], "목차 줄을 본문 시작으로 잡았습니다"
    assert text[start:].startswith("감사기준서 580 서면진술 목차")


def test_cross_reference_digits_are_not_read_as_standard_numbers():
    """'감사기준서 500 8은 ...' 이 추출 과정에서 '5008' 로 붙어 나온다."""
    text = (
        "감사기준서 5008 은 경영진측 전문가의 적격성을 다룬다\n" + _body("x") + "\n"
        "감사기준서 8004 은 재무제표가 특정목적체계에 따라 작성된 경우\n" + _body("y") + "\n"
        "감사기준서 5305 은 테스트 범위에 대한 지침을 준다\n" + _body("z")
    )
    assert bsr.find_sections(text, bsr.PATTERNS["audit"]) == []


def test_four_digit_standard_numbers_still_match():
    text = "감사기준서 1100 내부회계관리제도의 감사 목차\n" + _body("1100", 40)
    found = bsr.find_sections(text, bsr.PATTERNS["audit"])
    assert [n for _, n, _ in found] == ["1100"]


def test_section_starts_at_the_title_page_not_the_early_running_head():
    """머리말이 한 페이지 일찍 바뀌는 판본이 있다 (600호 부록 끝장에 610호 머리말)."""
    text = (
        "감사기준서 610 ‘내부감사인이 수행한 업무의 활용’\n"   # 앞 기준서 부록 페이지
        + _body("600부록", 30) + "\n"
        "감사기준서 610 내부감사인이 수행한 업무의 활용\n목차\n문단번호\n"  # 진짜 표제
        + "\n".join(
            ["감사기준서 610 ‘내부감사인이 수행한 업무의 활용’\n" + _body("610", 30)] * 4
        )
    )
    found = bsr.find_sections(text, bsr.PATTERNS["audit"])

    assert len(found) == 1
    start = found[0][0]
    assert "목차" in text[start:start + bsr.TOC_LOOKAHEAD]
    assert "600부록" not in text[start:]


def test_opening_quote_is_not_kept_in_the_title():
    text = "감사기준서 610 ‘내부감사인이 수행한 업무의 활용’ 목차\n" + _body("610", 40)
    found = bsr.find_sections(text, bsr.PATTERNS["audit"])
    assert found[0][2].startswith("내부감사인")
