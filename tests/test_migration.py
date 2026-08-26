"""컬럼 추가 마이그레이션 검증.

`create_all()` 은 없는 테이블만 만든다. 이미 있는 테이블에 모델 컬럼이
늘어난 것은 알아채지 못해, 모델만 고치고 서버를 켜면 조회 시점에
"no such column" 으로 터진다.

그렇다고 테이블을 다시 만들면 그 안의 데이터가 사라진다 — 이 프로젝트에서는
그게 가장 큰 손실이다. 한 번 실제로 겪었다. 그래서 **덧붙이기만** 한다.
"""

import sqlite3

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def legacy_db(tmp_path, monkeypatch):
    """reprt_code · report_nm 이 아직 없던 시절의 report_sections 를 만든다."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE report_sections (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            rcept_no VARCHAR,
            doc_label VARCHAR,
            bsns_year INTEGER,
            level INTEGER,
            title VARCHAR,
            parent VARCHAR,
            section_no VARCHAR,
            body TEXT,
            chars INTEGER,
            audit_relevant BOOLEAN,
            created_at DATETIME
        )
    """)
    conn.execute(
        "INSERT INTO report_sections (id, company_id, title, chars, body)"
        " VALUES (1, 7, '31. 특수관계자와의 거래', 4200, '소중한 본문')"
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr("app.db.database.engine", engine)
    return engine


def test_a_missing_column_is_added(legacy_db):
    from app.db.database import ensure_columns

    added = ensure_columns()

    assert "report_sections.reprt_code" in added
    assert "report_sections.report_nm" in added


def test_the_existing_rows_survive(legacy_db):
    """새 컬럼을 붙이자고 본문을 잃어서는 안 된다."""
    from app.db.database import ensure_columns

    ensure_columns()

    with legacy_db.connect() as conn:
        row = conn.execute(
            text("SELECT title, body, chars FROM report_sections WHERE id = 1")
        ).one()

    assert row.title == "31. 특수관계자와의 거래"
    assert row.body == "소중한 본문"
    assert row.chars == 4200


def test_the_new_column_reads_back_as_null(legacy_db):
    from app.db.database import ensure_columns

    ensure_columns()

    with legacy_db.connect() as conn:
        value = conn.execute(
            text("SELECT reprt_code FROM report_sections WHERE id = 1")
        ).scalar()

    assert value is None


def test_running_it_twice_changes_nothing(legacy_db):
    from app.db.database import ensure_columns

    ensure_columns()
    assert ensure_columns() == [], "두 번째 실행에서 또 컬럼을 붙였습니다"


def test_it_never_drops_a_column_the_model_no_longer_has(legacy_db):
    """모델에서 사라진 컬럼도 그대로 둔다 — 지우는 일은 하지 않는다."""
    from app.db.database import ensure_columns

    with legacy_db.begin() as conn:
        conn.execute(text("ALTER TABLE report_sections ADD COLUMN 옛컬럼 TEXT"))

    ensure_columns()

    names = {c["name"] for c in inspect(legacy_db).get_columns("report_sections")}
    assert "옛컬럼" in names


def test_a_table_that_does_not_exist_yet_is_left_to_create_all(legacy_db):
    """빈 DB 에 ensure_columns 만 돌려도 터지지 않아야 한다."""
    from app.db.database import ensure_columns

    ensure_columns()   # report_sections 외의 테이블은 아직 없다


def test_the_report_section_model_can_be_read_after_migration(legacy_db):
    """실제로 ORM 조회가 되는지까지 본다 — 이게 안 되면 화면이 500 이다."""
    from sqlalchemy.orm import Session

    from app.db.database import ensure_columns
    from app.db.models import ReportSection

    ensure_columns()

    with Session(legacy_db) as session:
        row = session.get(ReportSection, 1)
        assert row.title == "31. 특수관계자와의 거래"
        assert row.reprt_code is None
        assert row.report_label == "사업보고서", "옛 행은 사업보고서로 본다"
