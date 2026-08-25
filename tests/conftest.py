"""테스트가 실제 audit.db 를 건드리지 못하게 막는다.

과거에 test_company_routes.py 의 픽스처가 Base.metadata.drop_all(bind=engine)
을 부르면서 수집해 둔 데이터를 전부 날린 적이 있다. engine 이 실제 DB
(sqlite:///./audit.db)에 묶여 있었기 때문이다. 테스트는 73개 모두 통과했고,
데이터를 지우면서 초록불이 켜졌다.

pytest 는 테스트 모듈보다 conftest.py 를 먼저 읽는다. app.db.database 가
import 되기 전인 이 시점에 DB 주소를 임시 파일로 돌려놓는 것이 유일하게
안전한 지점이다. 아래 sessionstart 훅이 그 결과를 한 번 더 확인한다.
"""

import os
import pathlib
import tempfile

# ── 반드시 app 을 import 하기 전에 실행되어야 한다 ──────────────────
_TMP_DIR = pathlib.Path(tempfile.mkdtemp(prefix="audit-tests-"))
_TMP_DB = _TMP_DIR / "test.db"
os.environ["AUDIT_DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

import pytest  # noqa: E402

from app.db.database import DEFAULT_DATABASE_URL, engine  # noqa: E402


def pytest_sessionstart(session):
    """실제 DB에 붙어 있으면 테스트를 시작하지 않는다."""
    url = str(engine.url)
    real = DEFAULT_DATABASE_URL.replace("sqlite:///", "")

    if pathlib.Path(url.replace("sqlite:///", "")).name == pathlib.Path(real).name:
        raise RuntimeError(
            f"테스트가 실제 DB에 연결됐습니다: {url}\n"
            "conftest.py 가 AUDIT_DATABASE_URL 을 설정하기 전에 app.db.database 가 "
            "import 된 상태입니다. 테스트를 중단합니다 — 그대로 두면 drop_all 이 "
            "수집 데이터를 지웁니다."
        )


@pytest.fixture
def temp_db_path() -> pathlib.Path:
    """테스트용 DB 파일 경로 (진단이 필요할 때 쓴다)."""
    return _TMP_DB
