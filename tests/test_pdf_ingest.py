"""pdf_ingest 검증 테스트.

금감원 게시물은 같은 문서를 .hwp 와 .pdf 로 함께 첨부하고 HWP 링크가
먼저 나오는 경우가 많다. HWP를 .pdf 로 저장하면 pdfplumber가 열지 못해
raw_text가 비게 되므로, 우선순위와 매직바이트 검증이 모두 동작해야 한다.
"""

import pathlib

from app.crawler import pdf_ingest


def test_prefer_pdf_puts_pdf_first():
    attachments = [
        {"name": "지적사례.hwp", "url": "https://x/FileDown.do?atchFileId=1&fileSn=0"},
        {"name": "지적사례.pdf", "url": "https://x/FileDown.do?atchFileId=1&fileSn=1"},
    ]
    ordered = pdf_ingest.prefer_pdf(attachments)
    assert ordered[0]["name"] == "지적사례.pdf"
    assert ordered[1]["name"] == "지적사례.hwp"


def test_prefer_pdf_ranks_unknown_above_hwp():
    attachments = [
        {"name": "붙임.hwp", "url": "https://x/a.hwp"},
        {"name": "첨부", "url": "https://x/FileDown.do?atchFileId=9"},
    ]
    ordered = pdf_ingest.prefer_pdf(attachments)
    assert ordered[0]["name"] == "첨부"


def test_prefer_pdf_drops_unusable_entries():
    assert pdf_ingest.prefer_pdf([{"name": "url 없음"}, None, "문자열"]) == []


def test_is_pdf_file_detects_real_pdf(tmp_path: pathlib.Path):
    good = tmp_path / "good.pdf"
    good.write_bytes(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    assert pdf_ingest.is_pdf_file(str(good)) is True


def test_is_pdf_file_rejects_hwp_saved_as_pdf(tmp_path: pathlib.Path):
    # HWP 5.0 시그니처는 OLE 복합문서 헤더로 시작한다
    bad = tmp_path / "actually_hwp.pdf"
    bad.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 2048)
    assert pdf_ingest.is_pdf_file(str(bad)) is False


def test_is_pdf_file_handles_missing_file(tmp_path: pathlib.Path):
    assert pdf_ingest.is_pdf_file(str(tmp_path / "nope.pdf")) is False


def test_ingest_discards_non_pdf_so_next_attachment_can_retry(tmp_path: pathlib.Path):
    """HWP를 받으면 파일을 지우고 (None, None)을 돌려줘야 한다."""
    saved = tmp_path / "doc.pdf"

    def fake_download(url, uid, session=None):
        saved.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 2048)
        return str(saved)

    path, text = pdf_ingest.ingest(fake_download, "https://x/a.hwp", "doc")

    assert (path, text) == (None, None)
    assert not saved.exists(), "비-PDF 파일이 남으면 다음 크롤링에서 재시도가 막힌다"


def test_ingest_first_tries_pdf_before_hwp(tmp_path: pathlib.Path, monkeypatch):
    """PDF 첨부가 뒤에 있어도 먼저 시도해야 하고, 성공하면 HWP는 건드리지 않는다."""
    saved = tmp_path / "doc.pdf"
    calls = []

    def fake_download(url, uid, session=None):
        calls.append(url)
        body = b"\xd0\xcf\x11\xe0" if url.endswith(".hwp") else b"%PDF-1.7\n"
        saved.write_bytes(body + b"\x00" * 2048)
        return str(saved)

    monkeypatch.setattr(pdf_ingest.pdf_parser, "extract_text", lambda p: "본문")

    attachments = [
        {"name": "붙임.hwp", "url": "https://x/a.hwp"},
        {"name": "붙임.pdf", "url": "https://x/a.pdf"},
    ]
    path, text = pdf_ingest.ingest_first(attachments, fake_download, "doc", delay=0)

    assert text == "본문"
    assert calls == ["https://x/a.pdf"], "PDF를 먼저 시도해야 한다"


def test_ingest_first_falls_back_when_first_attachment_is_not_pdf(tmp_path, monkeypatch):
    """확장자를 알 수 없는 첨부가 HWP였다면 다음 첨부로 넘어가야 한다."""
    saved = tmp_path / "doc.pdf"
    calls = []

    def fake_download(url, uid, session=None):
        calls.append(url)
        body = b"\xd0\xcf\x11\xe0" if "fileSn=0" in url else b"%PDF-1.7\n"
        saved.write_bytes(body + b"\x00" * 2048)
        return str(saved)

    monkeypatch.setattr(pdf_ingest.pdf_parser, "extract_text", lambda p: "본문")

    # 둘 다 확장자가 드러나지 않는 fileDown 링크 — 내용으로만 판별해야 한다
    attachments = [
        {"name": "붙임1", "url": "https://x/FileDown.do?atchFileId=A&fileSn=0"},
        {"name": "붙임2", "url": "https://x/FileDown.do?atchFileId=A&fileSn=1"},
    ]
    path, text = pdf_ingest.ingest_first(attachments, fake_download, "doc", delay=0)

    assert text == "본문"
    assert len(calls) == 2, "첫 첨부가 HWP면 두 번째까지 시도해야 한다"


def test_ingest_first_uses_distinct_paths_per_attachment(tmp_path, monkeypatch):
    """download_pdf 의 exists() 캐시가 나머지 첨부를 가리면 안 된다.

    1순위 첨부가 유효한 PDF지만 텍스트가 없는 스캔본이면 파일이 남는다.
    모든 첨부가 같은 uid 를 쓰면 2순위 첨부를 요청해도 캐시된 같은 파일이
    돌아와 영원히 같은 실패를 반복하게 된다.
    """
    uids = []

    def fake_download(url, uid, session=None):
        uids.append(uid)
        p = tmp_path / f"{uid}.pdf"
        if p.exists():                      # 실제 download_pdf 의 캐시 동작 재현
            return str(p)
        p.write_bytes(b"%PDF-1.7\n" + b"\x00" * 2048)
        return str(p)

    # 1순위는 텍스트가 없는 스캔본, 2순위에 본문이 있다
    monkeypatch.setattr(
        pdf_ingest.pdf_parser, "extract_text",
        lambda p: "" if p.endswith("doc.pdf") else "본문",
    )

    attachments = [
        {"name": "스캔본", "url": "https://x/FileDown.do?fileSn=0"},
        {"name": "본문",   "url": "https://x/FileDown.do?fileSn=1"},
    ]
    path, text = pdf_ingest.ingest_first(attachments, fake_download, "doc", delay=0)

    assert uids == ["doc", "doc_1"], "첨부마다 다른 저장 경로를 써야 한다"
    assert text == "본문"


def test_ingest_first_returns_scanned_pdf_path_as_fallback(tmp_path, monkeypatch):
    """텍스트를 끝내 못 얻어도 받아둔 PDF 경로는 돌려준다."""
    def fake_download(url, uid, session=None):
        p = tmp_path / f"{uid}.pdf"
        p.write_bytes(b"%PDF-1.7\n" + b"\x00" * 2048)
        return str(p)

    monkeypatch.setattr(pdf_ingest.pdf_parser, "extract_text", lambda p: "")

    attachments = [{"name": "스캔본.pdf", "url": "https://x/a.pdf"}]
    path, text = pdf_ingest.ingest_first(attachments, fake_download, "doc", delay=0)

    assert text is None
    assert path and path.endswith("doc.pdf")
