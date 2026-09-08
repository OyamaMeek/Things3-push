"""Application entry point for the Things-to-Git synchronization service."""

import logging
import signal
from pathlib import Path

try:
    import dotenv
except ImportError:  # Keep the entry point importable before dependencies are installed.
    class _Dotenv:
        @staticmethod
        def load_dotenv() -> None:
            return None

    dotenv = _Dotenv()

from src.config import AppConfig
from src.service import build_service
from src.utils import setup_logging


logger = logging.getLogger(__name__)

# Module-level handle so signal handlers can reach the service even before it is
# constructed, and so tests can inject a fake service without touching signal state.
service_holder: dict = {}


def main() -> int:
    """Load configuration, run the service, and return a process exit code."""
    try:
        dotenv.load_dotenv()
        config = AppConfig.from_env()
    except Exception:
        logger.error("Configuration failed")
        return 2

    try:
        setup_logging(
            Path(__file__).resolve().parent / "logs",
            config.log_level,
            config.log_max_bytes,
            config.log_backup_count,
        )
        service = build_service(config)
        service_holder["service"] = service

        def handle_signal(signum, frame) -> None:
            del signum, frame
            service_holder.get("service").stop()
            logger.info("Shutdown requested")

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        service.run()
    except Exception:
        logger.error("Service failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
