from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_url: str = os.getenv("JOBFORGE_DB_URL", "sqlite:///./jobforge.db")
    secret_key: str = os.getenv("JOBFORGE_SECRET_KEY", "dev-only-change-me")
    scrape_interval_minutes: int = int(os.getenv("JOBFORGE_SCRAPE_INTERVAL_MINUTES", "120"))
    auto_refresh: bool = _bool("JOBFORGE_AUTO_REFRESH", True)
    llm_provider: str = os.getenv("JOBFORGE_LLM_PROVIDER", "ollama").lower()
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.5")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/").replace('://localhost:', '://127.0.0.1:')
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
    ollama_fast_model: str = os.getenv('OLLAMA_FAST_MODEL', 'qwen3.5:4b')
    ai_timeout_seconds: int = int(os.getenv('JOBFORGE_AI_TIMEOUT_SECONDS', '120'))
    enable_jobspy: bool = _bool("JOBFORGE_ENABLE_JOBSPY", False)


settings = Settings()
