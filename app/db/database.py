import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

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


def init_db():
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
