"""Configuration settings for Trade Store application."""

import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application runtime settings loaded from environment or defaults."""
    app_name: str = "Trade Store REST API"
    app_version: str = "1.0.0"
    db_path: str = os.getenv("TRADE_STORE_DB", "trade_store.db")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    scheduler_interval_seconds: int = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))
    enable_scheduler: bool = os.getenv("ENABLE_SCHEDULER", "True").lower() in ("true", "1", "yes")

    class Config:
        env_file = ".env"


settings = Settings()
