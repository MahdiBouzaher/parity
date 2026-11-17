import os
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parent.parent
ROOT = API_DIR.parent

load_dotenv(ROOT / ".env")
load_dotenv(API_DIR / ".env")


def _data_dir():
    raw = os.environ.get("PARITY_DATA_DIR", "./api/data")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / "parity.db"
DATASETS_DIR = DATA_DIR / "datasets"
KEYS_DIR = DATA_DIR / "keys"
SAMPLES_DIR = ROOT / "samples"
RUN_TIMEOUT = int(os.environ.get("PARITY_RUN_TIMEOUT", "30") or "30")
CORS_ORIGINS = [
    item.strip()
    for item in os.environ.get(
        "PARITY_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if item.strip()
]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 200000


def model_configured():
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def model_name():
    if not model_configured():
        return None
    return os.environ.get("OPENROUTER_MODEL", "").strip() or "openai/gpt-4o-mini"
