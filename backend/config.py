"""應用程式設定，機密值只允許由環境變數提供。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_URL = "sqlite+pysqlite:///./food_delivery.db"


class Settings(BaseSettings):
    """執行環境設定。"""

    database_url: str = DEFAULT_SQLITE_URL
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def use_sqlite_when_database_url_is_blank(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_SQLITE_URL
        return value

    def require_jwt_secret(self) -> str:
        """取得 JWT 密鑰；未設定時拒絕啟動認證功能。"""

        if self.jwt_secret_key is None:
            raise RuntimeError(
                "缺少 JWT_SECRET_KEY，請依 backend/.env.example 設定環境變數。"
            )
        secret = self.jwt_secret_key.get_secret_value()
        if not secret.strip():
            raise RuntimeError("JWT_SECRET_KEY 不可為空白。")
        if len(secret.encode("utf-8")) < 32:
            raise RuntimeError("JWT_SECRET_KEY 至少需要 32 bytes。")
        return secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
