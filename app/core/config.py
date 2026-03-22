from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "AUDIT"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "AUDIT Web Application"
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    ANTHROPIC_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
