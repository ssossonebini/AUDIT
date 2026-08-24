"""raw_text 가 비어 있는 레코드의 첨부 PDF를 다시 수집한다.

diagnose_pdf.py 로 "PDF 첨부가 존재한다"고 확인된 건을 실제로 채워 넣는 용도.
서버를 띄우지 않고 크롤링 경로와 동일한 pdf_ingest 헬퍼를 그대로 사용하므로,
여기서 성공하면 일반 크롤링에서도 성공한다.

사용법:
    python scripts/backfill_pdf.py --dry-run          # 대상만 확인
    python scripts/backfill_pdf.py                    # 전체 재수집
    python scripts/backfill_pdf.py --table fss_case
    python scripts/backfill_pdf.py --table fss --year 2026
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal                              # noqa: E402
from app.db.models import FssArticle, FssCaseReport, AuditNewsReport  # noqa: E402
from app.crawler import (                                             # noqa: E402
    fss_scraper, fss_case_scraper, audit_news_scraper, pdf_ingest,
)

TABLES = {
    "fss":        (FssArticle,      fss_scraper,        "중점심사"),
    "fss_case":   (FssCaseReport,   fss_case_scraper,   "지적사례"),
    "audit_news": (AuditNewsReport, audit_news_scraper, "감사 보도자료"),
}


def make_session(name: str, record):
    """audit_news 는 소스별로 다른 base_url 로 세션을 만든다."""
    if name != "audit_news":
        return TABLES[name][1]._session()
    base = (audit_news_scraper.FSS_BASE
            if getattr(record, "source", "FSS") == "FSS"
            else audit_news_scraper.FSC_BASE)
    return audit_news_scraper._session(base)


def fetch_attachments(name: str, record, key: str, session) -> list[dict]:
    """소스별 첨부 조회 방식 차이를 흡수한다."""
    if name == "fss":
        return fss_scraper.fetch_article_detail(key, session).get("attachments", [])
    if name == "fss_case":
        return fss_case_scraper.fetch_case_detail(key, session).get("attachments", [])
    raw = key.replace("FSS-", "").replace("FSC-", "")
    if getattr(record, "source", "FSS") == "FSS":
        return audit_news_scraper.fetch_fss_attachments(raw, session)
    return audit_news_scraper.fetch_fsc_attachments(raw, session)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", choices=list(TABLES), help="특정 테이블만 처리")
    ap.add_argument("--year", type=int, help="특정 연도만 처리")
    ap.add_argument("--limit", type=int, help="테이블당 최대 처리 건수")
    ap.add_argument("--dry-run", action="store_true", help="대상만 출력하고 종료")
    args = ap.parse_args()

    db = SessionLocal()
    targets = [args.table] if args.table else list(TABLES)
    grand_ok = grand_fail = 0

    for name in targets:
        model, _, label = TABLES[name]
        q = db.query(model).filter((model.raw_text.is_(None)) | (model.raw_text == ""))
        if args.year:
            q = q.filter(model.year == args.year)
        if args.limit:
            q = q.limit(args.limit)
        records = q.all()

        print(f"\n{'=' * 72}")
        print(f"  {label} ({name}) — 재수집 대상 {len(records)}건")
        print("=" * 72)

        if not records:
            print("  대상 없음 ✅")
            continue
        if args.dry_run:
            for rec in records:
                key = getattr(rec, "ntt_id", "")
                print(f"  [{getattr(rec, 'year', '?')}] {key}  {rec.title[:50]}")
            continue

        ok = fail = 0
        for rec in records:
            key = getattr(rec, "ntt_id", "") or ""
            print(f"\n▸ [{getattr(rec, 'year', '?')}] {rec.title[:52]}")
            print(f"  ntt_id={key}")

            try:
                session = make_session(name, rec)
                attachments = fetch_attachments(name, rec, key, session)
            except Exception as e:
                print(f"  ❌ 첨부 조회 실패: {type(e).__name__}: {e}")
                fail += 1
                continue

            if not attachments:
                print("  ❌ 첨부파일 없음")
                fail += 1
                continue

            download_fn = TABLES[name][1].download_pdf
            pdf_path, raw_text = pdf_ingest.ingest_first(
                attachments, download_fn, key, session,
            )

            if raw_text:
                rec.pdf_path, rec.raw_text = pdf_path, raw_text
                db.commit()
                print(f"  ✅ 수집 성공 — {len(raw_text):,}자  ({pdf_path})")
                ok += 1
            else:
                print("  ❌ PDF 본문 추출 실패 (HWP 전용 게시물 또는 스캔본)")
                fail += 1

            time.sleep(0.5)

        print(f"\n  {label} 결과: 성공 {ok}건 / 실패 {fail}건")
        grand_ok += ok
        grand_fail += fail

    db.close()

    if not args.dry_run:
        print(f"\n{'=' * 72}")
        print(f"전체 결과: 성공 {grand_ok}건 / 실패 {grand_fail}건")
        print("=" * 72)


if __name__ == "__main__":
    main()
