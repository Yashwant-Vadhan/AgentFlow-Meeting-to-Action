"""
Configuration module — loads environment variables via pydantic-settings.

All secrets and connection settings come from .env (never hardcoded).
See .env.example for the full list of supported variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve .env file path — look in project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unexpected env vars
    )

    # ── LLM (Ollama) ──────────────────────────────
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # ── Whisper STT ───────────────────────────────
    whisper_model_size: str = "medium"
    whisper_device: str = "cpu"

    # ── Database ──────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./meeting_to_action.db"

    # ── n8n Webhook ───────────────────────────────
    n8n_webhook_url: str = "http://localhost:5678/webhook/verified-task"

    # ── Trello ────────────────────────────────────
    trello_api_key: str = ""
    trello_token: str = ""
    trello_board_id: str = ""
    trello_list_id: str = ""

    # ── Discord Notifications ────────────────────
    discord_webhook_url: str = ""

    # ── Google Calendar (optional) ────────────────
    google_calendar_credentials_path: str = ""
    google_calendar_id: str = "primary"

    # ── Backend Server ────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # ── Audio Upload ──────────────────────────────
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 200

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
