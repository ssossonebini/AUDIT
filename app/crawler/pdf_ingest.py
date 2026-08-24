"""PDF 수집 공통 헬퍼.

크롤링 시점에 첨부 PDF를 내려받아 텍스트를 추출한다.
AI 요약 기능을 제거한 뒤에도 raw_text(PDF 전문)는 반드시 남아야 하므로,
모든 소스의 크롤링 경로에서 이 모듈을 사용한다.

주의: 금감원·금융위 게시물은 같은 문서를 .hwp 와 .pdf 두 형식으로 첨부하며
HTML에서 HWP 링크가 먼저 나오는 경우가 많다. 확장자만 믿으면 HWP를 .pdf 로
저장하게 되고 pdfplumber가 열지 못해 raw_text가 비게 된다.
따라서 (1) PDF로 보이는 첨부를 먼저 시도하고 (2) 내려받은 내용의 매직바이트를
검증한다.
"""

import logging
import os
import time
from typing import Callable, Iterable, Optional, Tuple

from app.crawler import pdf_parser

logger = logging.getLogger(__name__)

MAX_RAW_TEXT = 50000
PDF_MAGIC = b"%PDF"

# 명백히 PDF가 아닌 첨부 (한글·워드·엑셀·압축)
NON_PDF_EXT = (".hwp", ".hwpx", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".ppt", ".pptx")


def is_pdf_file(path: str) -> bool:
    """파일 선두 매직바이트로 실제 PDF 여부를 판정한다."""
    try:
        with open(path, "rb") as f:
            return f.read(5).startswith(PDF_MAGIC)
    except OSError:
        return False


def ingest(
    download_fn: Callable[..., Optional[str]],
    url: str,
    uid: str,
    session=None,
) -> Tuple[Optional[str], Optional[str]]:
    """단일 URL을 내려받아 PDF임을 확인한 뒤 텍스트를 추출한다.

    PDF가 아니면 파일을 지워 다음 시도(다른 첨부·다음 크롤링)를 막지 않는다.

    Returns:
        (pdf_path, raw_text) — 실패 시 (None, None)
    """
    if not url:
        return None, None

    try:
        path = download_fn(url, uid, session) if session is not None else download_fn(url, uid)
        if not path:
            return None, None

        if not is_pdf_file(path):
            logger.warning(f"PDF가 아닌 첨부 — 폐기하고 다음 첨부 시도: {url}")
            _discard(path)
            return None, None

        text = pdf_parser.extract_text(path)
        if not text:
            logger.warning(f"PDF 텍스트 추출 실패(스캔본 가능성): {path}")
            return path, None

        return path, text[:MAX_RAW_TEXT]

    except Exception as e:
        logger.warning(f"PDF 수집 실패 ({url}): {e}")
        return None, None


def ingest_first(
    attachments: Iterable[dict],
    download_fn: Callable[..., Optional[str]],
    uid: str,
    session=None,
    delay: float = 0.5,
) -> Tuple[Optional[str], Optional[str]]:
    """첨부 목록에서 텍스트 추출에 성공하는 첫 PDF를 수집한다.

    PDF로 보이는 첨부를 먼저 시도하고, HWP 등은 뒤로 미룬다.

    Returns:
        (pdf_path, raw_text) — 실패 시 (None, None)
    """
    fallback_path = None

    for i, att in enumerate(prefer_pdf(attachments)):
        url = att.get("url", "")
        if not url:
            continue

        # 첨부마다 저장 경로를 분리한다. download_pdf 는 {uid}.pdf 가 이미
        # 있으면 내려받지 않고 그 경로를 돌려주므로, 모든 첨부가 같은 uid 를
        # 쓰면 첫 첨부 파일이 계속 반환되어 나머지 첨부를 시도할 수 없다.
        # (본문 없는 스캔본 PDF가 1순위로 걸렸을 때 실제로 문제가 된다)
        slot = uid if i == 0 else f"{uid}_{i}"

        path, text = ingest(download_fn, url, slot, session)
        if text:
            return path, text

        # 유효한 PDF지만 텍스트가 없는 경우(스캔본) — 경로만이라도 남긴다
        if path and fallback_path is None:
            fallback_path = path

        if delay:
            time.sleep(delay)

    return fallback_path, None


def prefer_pdf(attachments: Iterable[dict]) -> list[dict]:
    """PDF로 보이는 첨부를 앞으로, 비-PDF 확장자를 뒤로 정렬한다."""
    items = [a for a in (attachments or []) if isinstance(a, dict) and a.get("url")]
    return sorted(items, key=_priority)


def _priority(att: dict) -> int:
    hint = f"{att.get('name', '')} {att.get('url', '')}".lower()
    if ".pdf" in hint:
        return 0                      # 확실한 PDF
    if any(ext in hint for ext in NON_PDF_EXT):
        return 2                      # 확실히 PDF 아님 — 마지막에만 시도
    return 1                          # 판단 불가 (fileDown 링크 등)


def _discard(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
