"""
PDF 텍스트 추출 및 중점심사 회계이슈 파싱
"""
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_text(pdf_path: str) -> str:
    """PDF에서 전체 텍스트 추출"""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"PDF 텍스트 추출 실패 ({pdf_path}): {e}")
        return ""


def parse_audit_issues(text: str) -> list[dict]:
    """
    PDF 텍스트에서 중점심사 회계이슈 항목 추출.
    금감원 보도자료는 아래 패턴 중 하나를 사용:
      ① 수익인식  ② 현금및현금성자산  ③ ...  ④ ...
      1. 수익인식  2. 현금및현금성자산  ...
      [이슈1] 수익인식  [이슈2] ...
    """
    issues = []

    # 패턴 1: 원문자 ①②③④⑤
    circle_patterns = {
        1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤",
        6: "⑥", 7: "⑦", 8: "⑧", 9: "⑨", 10: "⑩",
    }
    circle_chars = "".join(circle_patterns.values())
    circle_split = re.split(rf"[{circle_chars}]", text)

    if len(circle_split) > 2:
        for i, part in enumerate(circle_split[1:], 1):
            lines = part.strip().split("\n")
            title = lines[0].strip().rstrip(":")
            description = "\n".join(lines[1:]).strip()
            if title:
                issues.append({
                    "issue_number": i,
                    "issue_title": _clean(title),
                    "description": _clean(description[:1000]),
                })
        if issues:
            return issues

    # 패턴 2: "이슈 N:", "이슈N.", "(이슈 N)" 형태
    issue_pattern = re.findall(
        r"(?:이슈\s*(\d+)|회계이슈\s*(\d+))[.\s:）)]+([^\n]+)",
        text,
    )
    if issue_pattern:
        for match in issue_pattern:
            num = int(match[0] or match[1])
            title = match[2].strip()
            issues.append({
                "issue_number": num,
                "issue_title": _clean(title),
                "description": "",
            })
        if issues:
            return issues

    # 패턴 3: 번호 매김 "1. 제목\n내용"
    numbered = re.split(r"\n(?=\d+\.\s+[가-힣A-Za-z])", text)
    if len(numbered) > 2:
        for part in numbered[1:6]:
            m = re.match(r"(\d+)\.\s+(.+?)(?:\n|$)", part, re.DOTALL)
            if m:
                num = int(m.group(1))
                rest = part[m.end():]
                # 제목은 첫 줄, 설명은 그 이후
                title_line = m.group(2).strip()
                desc_lines = [l.strip() for l in rest.split("\n") if l.strip()]
                description = " ".join(desc_lines[:5])
                issues.append({
                    "issue_number": num,
                    "issue_title": _clean(title_line),
                    "description": _clean(description[:800]),
                })
        if len(issues) >= 2:
            return issues

    return issues


def build_summary(text: str, issues: list[dict]) -> str:
    """보도자료 요약 생성"""
    lines = []

    # 발표 배경 추출 (첫 몇 줄)
    first_para = _extract_first_paragraph(text)
    if first_para:
        lines.append(first_para)

    # 이슈 목록
    if issues:
        lines.append("\n【중점심사 회계이슈】")
        for issue in issues:
            lines.append(f"  {issue['issue_number']}. {issue['issue_title']}")
            if issue.get("description"):
                short_desc = issue["description"][:150].replace("\n", " ")
                lines.append(f"     └ {short_desc}")

    return "\n".join(lines)


def _extract_first_paragraph(text: str) -> str:
    """텍스트에서 첫 번째 의미있는 단락 추출"""
    skip_patterns = [
        r"^\s*\d+\s*$",          # 페이지 번호
        r"^\s*-\s*\d+\s*-\s*$",  # - 1 -
        r"^\s*보\s*도\s*자\s*료", # 제목
    ]
    paragraphs = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) < 10:
            continue
        if any(re.match(p, line) for p in skip_patterns):
            continue
        paragraphs.append(line)
        if len("\n".join(paragraphs)) > 200:
            break

    return " ".join(paragraphs[:3])


def _clean(text: str) -> str:
    """불필요한 공백 및 특수문자 정리"""
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text
