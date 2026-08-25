from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "AUDIT"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "AUDIT Web Application"
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # 외부 API 키 — 모두 .env 에서 읽는다 (.env 는 gitignore)
    ANTHROPIC_API_KEY: Optional[str] = None   # 보도자료 AI 분류
    DART_API_KEY: Optional[str] = None        # OPEN DART 재무제표 조회

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
