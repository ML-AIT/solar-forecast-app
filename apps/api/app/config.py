"""Application settings, read from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    # Comma-separated list, e.g. "http://localhost:3000,https://solar.example.com"
    allowed_origins: str = "http://localhost:3000"
    forecast_provider: Literal["demo", "file"] = "demo"
    forecast_dir: Path = Path("./forecasts")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
