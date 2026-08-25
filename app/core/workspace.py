"""회사별 작업폴더 관리.

workspace/ 는 gitignore 다. 재무제표·뉴스·카드뉴스가 쌓이는 로컬 전용 폴더이며,
Claude Code 가 분석할 때 직접 읽는 진입점이기도 하다.

    workspace/2026_삼성전자/
    ├── 00_INPUT.md          분석 진입점 (내보내기 기능이 생성)
    ├── 01_financials/       DART 재무제표
    ├── 02_news/             뉴스 크롤링 결과
    ├── 03_regulatory/       중점심사·지적사례 발췌
    └── 04_output/           분석결과·카드뉴스
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("workspace")
SUBDIRS = ("01_financials", "02_news", "03_regulatory", "04_output")

# Windows 에서 파일명에 쓸 수 없는 문자
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str) -> str:
    """회사명을 폴더명으로 쓸 수 있게 다듬는다."""
    cleaned = _UNSAFE.sub("", name).strip().rstrip(".")
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:60] or "unnamed"


def folder_name(audit_year: int, corp_name: str) -> str:
    return f"{audit_year}_{safe_name(corp_name)}"


def create(audit_year: int, corp_name: str) -> Path:
    """작업폴더와 하위 구조를 만든다. 이미 있으면 그대로 둔다."""
    root = WORKSPACE_ROOT / folder_name(audit_year, corp_name)
    for sub in SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)

    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(
            f"""# {corp_name} — {audit_year}년 감사

| 폴더 | 담을 것 |
|---|---|
| `01_financials/` | DART 재무제표 (웹호스트가 수집) |
| `02_news/` | 뉴스 크롤링 결과 |
| `03_regulatory/` | 중점심사·지적사례 중 이 회사 관련 항목 |
| `04_output/` | 분석결과·카드뉴스 |

분석은 Claude Code 에서 이 폴더를 읽어 수행한다.
""",
            encoding="utf-8",
        )

    logger.info(f"작업폴더 준비: {root}")
    return root


def path_for(audit_year: int, corp_name: str) -> Path:
    return WORKSPACE_ROOT / folder_name(audit_year, corp_name)
