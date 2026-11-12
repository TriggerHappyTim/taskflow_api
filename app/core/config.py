"""Централизованный конфиг приложения.

Все секреты читаются только из переменных окружения / .env
(pydantic-settings). В коде не должно быть жёстко зашитых токенов и URL.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Приложение ---
    APP_NAME: str = "TaskFlow API"
    DEBUG: bool = False

    # --- База данных ---
    # Локально: sqlite+aiosqlite:///./taskflow.db
    # В Docker/Postgres: postgresql+asyncpg://user:pass@db:5432/taskflow
    DATABASE_URL: str = "sqlite+aiosqlite:///./taskflow.db"

    # --- JWT / авторизация ---
    SECRET_KEY: str = "change-me-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""
    TELEGRAM_PROXY: str = ""  # например http://127.0.0.1:8080 (api.telegram.org блокируется из РФ)

    # --- MAX (см. раздел 6 плана) ---
    MAX_BOT_TOKEN: str = ""
    MAX_API_URL: str = "https://platform-api2.max.ru"
    MAX_WEBHOOK_SECRET: str = ""


settings = Settings()
