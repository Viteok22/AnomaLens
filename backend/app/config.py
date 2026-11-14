from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "skab"
ARTIFACTS = BACKEND_DIR / "artifacts"
DB_PATH = BACKEND_DIR / "monitor.db"

load_dotenv(BACKEND_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()

CALIBRATION_ROWS = 100
ALERT_PERSISTENCE = 15
# 5 минут нормального сигнала при 1 Гц. Автозакрытие — только вместе
# с подтверждением оператором.
RESOLVE_PERSISTENCE = 300
DEFAULT_SPEED = 10.0
MAX_SPEED = 30.0
