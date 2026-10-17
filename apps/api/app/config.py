"""Application settings (pydantic-settings).

Local-first defaults: SQLite database, loopback binding, no telemetry, no keys.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Unprefixed compatibility aliases (the repository's .env.example historically
# used bare names). EGA_-prefixed values always win.
_ENV_ALIASES: dict[str, str] = {
    "DATABASE_URL": "database_url",
    "ENVIRONMENT": "environment",
    "DEFAULT_MODEL_PROVIDER": "default_provider",
    "OLLAMA_BASE_URL": "ollama_base_url",
    "OLLAMA_DEFAULT_MODEL": "ollama_default_model",
    "APP_ENCRYPTION_KEY": "app_encryption_key",
    "HOST": "host",
    "PORT": "port",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EGA_", extra="ignore")

    app_name: str = "EntityGraph Auditor"
    version: str = "0.1.0"
    environment: str = "development"

    # storage
    database_url: str = "sqlite:///./var/ega.db"
    data_dir: Path = Path("./var")

    # security
    app_encryption_key: str = ""  # base64/urlsafe key material for secret encryption
    allow_private_urls: bool = False  # SSRF gate: private/loopback fetches only if True
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3100,http://127.0.0.1:3100"
    )
    docs_enabled: bool = True
    auth_token: str = ""  # optional single-user gate for remote access ("" = disabled)
    max_upload_bytes: int = 10_000_000
    max_fetch_bytes: int = 5_000_000
    fetch_timeout_s: float = 10.0
    respect_robots: bool = True

    # audit execution
    audit_timeout_s: int = 600
    cache_enabled: bool = True
    deterministic_only: bool = False  # force no-LLM mode regardless of provider config
    log_content: bool = False  # never log raw page content unless explicitly opted in
    max_repair_loops: int = 2  # critic repair loops (PRD §8.2 agent 13)

    # model defaults
    default_provider: str = "null"
    default_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = ""

    # server binding (used by uvicorn/Docker entrypoints)
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def multi_user(self) -> bool:
        return bool(self.auth_token)


def _apply_env_aliases() -> None:
    """Honour unprefixed env var names when the EGA_-prefixed one is absent."""
    for bare, field in _ENV_ALIASES.items():
        if bare in os.environ and f"EGA_{bare}" not in os.environ:
            os.environ.setdefault(f"EGA_{field}", os.environ[bare])


@lru_cache
def get_settings() -> Settings:
    _apply_env_aliases()
    return Settings()


def ensure_data_dir(settings: Settings | None = None) -> Path:
    s = settings or get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s.data_dir
