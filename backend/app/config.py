"""Environment configuration. All values can be overridden with ELDERCARE_* env vars."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ELDERCARE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./eldercare.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontend_base_url: str = "http://localhost:5173"

    # Token validity window around the scheduled visit (architecture.md section 8).
    token_window_before_min: int = 30
    token_window_after_hours: int = 2

    brief_max_lines: int = 6

    data_dir: Path = REPO_ROOT / "data"
    seed_on_startup: bool = True


settings = Settings()
