from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pricetracker"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/pricetracker"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Email (SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # LLM fallback
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # App
    app_name: str = "Price Tracker"
    frontend_url: str = "http://localhost:5173"
    debug: bool = False
    # Default check interval for Beat schedule (can be overridden in .env)
    check_interval_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
