"""PDF 수집 공통 헬퍼.

크롤링 시점에 첨부 PDF를 내려받아 텍스트를 추출한다.
AI 요약 기능을 제거한 뒤에도 raw_text(PDF 전문)는 반드시 남아야 하므로,
모든 소스의 크롤링 경로에서 이 모듈을 사용한다.
"""

import logging
import time
from typing import Callable, Iterable, Optional, Tuple

from app.crawler import pdf_parser

logger = logging.getLogger(__name__)

MAX_RAW_TEXT = 50000


def ingest(
    download_fn: Callable[..., Optional[str]],
    url: str,
    uid: str,
    session=None,
) -> Tuple[Optional[str], Optional[str]]:
    """단일 PDF URL을 내려받아 텍스트를 추출한다.

    Returns:
        (pdf_path, raw_text) — 실패 시 (None, None)
    """
    if not url:
        return None, None

    try:
        path = download_fn(url, uid, session) if session is not None else download_fn(url, uid)
        if not path:
            return None, None

        text = pdf_parser.extract_text(path)
        if not text:
            logger.warning(f"PDF 텍스트 추출 실패: {path}")
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

    Returns:
        (pdf_path, raw_text) — 실패 시 (None, None)
    """
    for att in attachments or []:
        url = att.get("url", "")
        if not _looks_like_pdf(url):
            continue

        path, text = ingest(download_fn, url, uid, session)
        if text:
            return path, text

        if delay:
            time.sleep(delay)

    return None, None


def _looks_like_pdf(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return ".pdf" in lowered or "filedown" in lowered or "atchfileid" in lowered
