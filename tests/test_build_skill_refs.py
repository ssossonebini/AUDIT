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
