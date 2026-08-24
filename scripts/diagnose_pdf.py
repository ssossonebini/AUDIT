"""첨부 PDF 수집 실패 원인 진단 스크립트.

raw_text 가 비어 있는 레코드에 대해 실제 게시물의 첨부파일을 조회하고,
각 첨부를 내려받아 "진짜 PDF 인지"를 매직바이트로 확인한다.
파일을 저장하지 않으므로 downloads/ 를 건드리지 않는다.

사용법:
    python scripts/diagnose_pdf.py               # raw_text 없는 것 전부
    python scripts/diagnose_pdf.py --year 2026   # 특정 연도만
    python scripts/diagnose_pdf.py --table fss_case --limit 3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal                      # noqa: E402
from app.db.models import FssArticle, FssCaseReport, AuditNewsReport  # noqa: E402
from app.crawler import fss_scraper, fss_case_scraper, audit_news_scraper, pdf_ingest  # noqa: E402

SIGNATURES = [
    (b"%PDF",                         "PDF"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "HWP 5.0 / MS Office (OLE 복합문서)"),
    (b"PK\x03\x04",                   "ZIP 계열 (HWPX / DOCX / XLSX)"),
    (b"<!DOCTYPE",                    "HTML (오류 페이지 가능성)"),
    (b"<html",                        "HTML (오류 페이지 가능성)"),
]

TABLES = {
    "fss":       (FssArticle,      fss_scraper,        "중점심사"),
    "fss_case":  (FssCaseReport,   fss_case_scraper,   "지적사례"),
    "audit_news": (AuditNewsReport, audit_news_scraper, "감사 보도자료"),
}


def identify(head: bytes) -> str:
    for magic, label in SIGNATURES:
        if head.startswith(magic):
            return label
    return f"알 수 없음 (선두 바이트: {head[:8]!r})"


def fetch_attachments(scraper, record, key: str):
    """소스별 첨부 조회 방식 차이를 흡수한다."""
    if hasattr(scraper, "fetch_article_detail"):
        return scraper.fetch_article_detail(key).get("attachments", [])
    if hasattr(scraper, "fetch_case_detail"):
        return scraper.fetch_case_detail(key).get("attachments", [])
    raw = key.replace("FSS-", "").replace("FSC-", "")
    if getattr(record, "source", "FSS") == "FSS":
        return scraper.fetch_fss_attachments(raw)
    return scraper.fetch_fsc_attachments(raw)


def probe(session, url: str) -> str:
    """저장하지 않고 선두 바이트만 받아 형식을 판정한다."""
    try:
        resp = session.get(url, timeout=30, stream=True)
        head = next(resp.iter_content(chunk_size=512), b"")
        ctype = resp.headers.get("Content-Type", "?")
        cdisp = resp.headers.get("Content-Disposition", "")
        resp.close()

        filename = ""
        if "filename" in cdisp:
            filename = cdisp.split("filename")[-1].strip('=;"\' ')[:60]

        return f"{identify(head)}\n        Content-Type: {ctype}" + (
            f"\n        파일명: {filename}" if filename else ""
        )
    except Exception as e:
        return f"요청 실패 — {type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", choices=list(TABLES), help="특정 테이블만 검사")
    ap.add_argument("--year", type=int, help="특정 연도만 검사")
    ap.add_argument("--limit", type=int, default=5, help="테이블당 최대 검사 건수")
    args = ap.parse_args()

    db = SessionLocal()
    targets = [args.table] if args.table else list(TABLES)

    for name in targets:
        model, scraper, label = TABLES[name]
        q = db.query(model).filter((model.raw_text.is_(None)) | (model.raw_text == ""))
        if args.year:
            q = q.filter(model.year == args.year)
        records = q.limit(args.limit).all()

        print(f"\n{'=' * 72}")
        print(f"  {label} ({name}) — 본문 미수집 {len(records)}건")
        print("=" * 72)

        if not records:
            print("  검사 대상 없음 ✅")
            continue

        session = scraper._session()

        for rec in records:
            key = getattr(rec, "ntt_id", None) or getattr(rec, "standard_id", "")
            print(f"\n▸ [{getattr(rec, 'year', '?')}] {rec.title[:56]}")
            print(f"  ntt_id={key}  url={getattr(rec, 'url', '')}")

            try:
                attachments = fetch_attachments(scraper, rec, key)
            except Exception as e:
                print(f"  ❌ 상세 페이지 조회 실패: {type(e).__name__}: {e}")
                continue

            if not attachments:
                print("  ❌ 첨부파일을 하나도 찾지 못함 "
                      "→ 게시물 HTML 구조가 바뀌었거나 첨부가 없는 게시물")
                continue

            ordered = pdf_ingest.prefer_pdf(attachments)
            print(f"  첨부 {len(attachments)}건 (수집 시도 순서대로):")

            for i, att in enumerate(ordered, 1):
                print(f"    {i}. {att.get('name', '(이름없음)')[:50]}")
                print(f"       {att['url'][:88]}")
                print(f"       → {probe(session, att['url'])}")

    db.close()
    print(f"\n{'=' * 72}")
    print("판정 기준: 'PDF' 로 표시된 첨부가 하나라도 있으면 재수집으로 해결됩니다.")
    print("모두 HWP/ZIP 이면 해당 게시물은 PDF 첨부가 없는 것이므로")
    print("HWP 파서 도입 또는 원문 직접 확인이 필요합니다.")
    print("=" * 72)


if __name__ == "__main__":
    main()
