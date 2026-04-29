from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
HISTORY_DIR = PROJECT_ROOT / "history"
CACHE_DIR = PROJECT_ROOT / ".cache"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"
DEEPSEEK_DEFAULT_THINKING = "disabled"
DEEPSEEK_LEGACY_MODEL_ALIASES = {
    "deepseek-chat": (DEEPSEEK_DEFAULT_MODEL, "disabled"),
    "deepseek-reasoner": (DEEPSEEK_DEFAULT_MODEL, "enabled"),
}

NCBI_EMAIL = os.getenv("NCBI_EMAIL", "researcher@bio-precision-agent.local")
MAX_EVIDENCE_CHARS = 24000
WEB_TIMEOUT_SECONDS = 12
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7


def ensure_runtime_dirs() -> None:
    HISTORY_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    if not ENV_PATH.exists():
        ENV_PATH.touch()
