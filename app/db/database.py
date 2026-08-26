import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)

# 테스트는 tests/conftest.py 가 이 환경변수를 임시 파일로 바꿔 실제 DB를 지키게 한다.
# 기본값은 평소 쓰는 로컬 DB다.
DEFAULT_DATABASE_URL = "sqlite:///./audit.db"
DATABASE_URL = os.getenv("AUDIT_DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns():
    """모델에 새로 생긴 컬럼을 기존 테이블에 덧붙인다.

    `create_all()` 은 **없는 테이블만** 만든다. 이미 있는 테이블에 컬럼이
    늘어난 것은 알아채지 못하므로, 모델만 고치고 서버를 켜면 조회 시점에
    "no such column" 으로 터진다. 그렇다고 테이블을 다시 만들면 그 안의
    데이터가 사라진다 — 이 프로젝트에서는 그게 가장 큰 손실이다.

    그래서 **덧붙이기만** 한다. 컬럼을 지우거나 형을 바꾸는 일은 하지 않으므로
    기존 데이터는 어떤 경우에도 그대로 남는다. 새 컬럼은 NULL 로 채워진다.
    """
    from sqlalchemy import inspect, text

    from app.db import models  # noqa: F401 — 임포트해야 Base 에 테이블이 등록된다

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added: list[str] = []

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue                      # create_all 이 통째로 만든다

            have = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue

                ddl = column.type.compile(engine.dialect)
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}')
                )
                added.append(f"{table.name}.{column.name}")

    if added:
        logger.info(f"컬럼을 추가했습니다: {', '.join(added)}")
    return added


def init_db():
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    ensure_columns()
