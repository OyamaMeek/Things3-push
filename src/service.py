"""Run the Things snapshot sync and own its background components."""

import logging
import threading
from typing import Optional

from .config import AppConfig
from .git_ops import GitClient
from .sync_engine import SyncEngine
from .things_adapter import ThingsReader, discover_database_path, load_default_api
from .watcher import DatabaseWatcher, DebouncedSync


logger = logging.getLogger(__name__)


class SyncService:
    """Coordinate startup, periodic synchronization, and graceful shutdown."""

    def __init__(
        self,
        engine,
        watcher,
        debouncer,
        full_sync_interval: float,
        stop_event: Optional[object] = None,
    ) -> None:
        self.engine = engine
        self.watcher = watcher
        self.debouncer = debouncer
        self.full_sync_interval = full_sync_interval
        self.stop_event = stop_event if stop_event is not None else threading.Event()
        self._stop_lock = threading.RLock()
        self._stop_requested = False

    def run(self) -> None:
        """Perform the initial sync, then run periodic full syncs until stopped."""
        self.engine.sync()
        try:
            if not self._is_stop_requested():
                self.watcher.start()
                if not self._is_stop_requested():
                    while True:
                        wait_result = self.stop_event.wait(self.full_sync_interval)
                        if wait_result or self._is_stop_requested():
                            break
                        try:
                            self.engine.sync()
                        except Exception:
                            logger.error("Scheduled full sync failed")
                        if self._is_stop_requested():
                            break
        except BaseException:
            self._cleanup(suppress_errors=True)
            raise
        else:
            self._cleanup(suppress_errors=False)

    def _is_stop_requested(self) -> bool:
        with self._stop_lock:
            return self._stop_requested or self.stop_event.is_set()

    def _cleanup(self, *, suppress_errors: bool) -> None:
        errors = []
        try:
            self.watcher.stop()
        except Exception as error:
            errors.append(error)
            if suppress_errors:
                logger.error("Watcher cleanup failed")
        try:
            self.debouncer.stop(wait=True)
        except Exception as error:
            errors.append(error)
            if suppress_errors:
                logger.error("Debouncer cleanup failed")
        if errors and not suppress_errors:
            raise errors[0]

    def stop(self) -> None:
        """Request shutdown once; repeated requests have no additional effect."""
        with self._stop_lock:
            if self._stop_requested:
                return
            self._stop_requested = True
        self.stop_event.set()


def build_service(config: AppConfig) -> SyncService:
    """Construct the complete service graph from application configuration."""
    database_path = discover_database_path(config.things_db)
    reader = ThingsReader(load_default_api(), database_path)
    git_client = GitClient(config.repo_path, timeout=config.git_timeout_seconds)
    engine = SyncEngine(config, reader, git_client)
    debouncer = DebouncedSync(engine.sync_if_idle, config.watch_debounce_seconds)
    watcher = DatabaseWatcher(database_path, debouncer)
    return SyncService(engine, watcher, debouncer, config.full_sync_interval)
