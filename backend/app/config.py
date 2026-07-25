from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Bizfluence"
    database_url: str = "sqlite:///./bizfluence.db"
    cors_origins: str = "http://localhost:3000,https://bizfluence.vercel.app"
    gemini_api_key: str = ""
    hunter_api_key: str = ""
    resend_api_key: str = ""
    resend_from_email: str = "Bizfluence <onboarding@resend.dev>"
    seed_on_startup: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
