import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_INVALID_PATH_CHARS = re.compile(r'[/:?*<>|"\x00-\x1f]')

def parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}: return True
    if value in {"0", "false", "no", "off"}: return False
    raise ValueError(f"{name} must be true or false")

def sanitize_path_segment(title: str, fallback: str, max_length: int = 120) -> str:
    value = _INVALID_PATH_CHARS.sub("-", title).strip().rstrip(".").strip()
    value = value or fallback
    return value[:max_length].rstrip(".").strip() or fallback[:max_length]

def setup_logging(log_dir: Path, level: str, max_bytes: int, backup_count: int) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(log_dir / "sync.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    stream_handler = logging.StreamHandler()
    file_handler.setFormatter(formatter); stream_handler.setFormatter(formatter)
    logging.basicConfig(level=getattr(logging, level.upper()), handlers=[file_handler, stream_handler], force=True)
