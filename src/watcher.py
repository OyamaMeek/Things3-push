"""Watch the Things database and schedule serialized, debounced syncs."""

import logging
import threading
from pathlib import Path
from typing import Callable, Set, Tuple

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # Keep imports usable for environments before dependencies are installed.
    class FileSystemEventHandler:
        pass

    class Observer:
        def __init__(self, *args, **kwargs):
            raise ImportError("watchdog is required to observe filesystem changes")


_LOG = logging.getLogger(__name__)


def _normalize_path(path: object) -> Path:
    return Path(path).expanduser().resolve()


class DatabaseEventFilter(FileSystemEventHandler):
    """Forward events for the database and SQLite's sidecar files only."""

    def __init__(self, database_path: Path, request_sync: Callable[[], None]) -> None:
        super().__init__()
        database = _normalize_path(database_path)
        self._request_sync = request_sync
        self._paths: Set[Path] = {
            database,
            database.with_name(database.name + "-wal"),
            database.with_name(database.name + "-shm"),
        }

    def _handle(self, event, paths: Tuple[object, ...]) -> None:
        if getattr(event, "is_directory", False):
            return
        if any(path and _normalize_path(path) in self._paths for path in paths):
            self._request_sync()

    def on_modified(self, event) -> None:
        self._handle(event, (getattr(event, "src_path", None),))

    def on_created(self, event) -> None:
        self._handle(event, (getattr(event, "src_path", None),))

    def on_deleted(self, event) -> None:
        self._handle(event, (getattr(event, "src_path", None),))

    def on_moved(self, event) -> None:
        self._handle(
            event,
            (
                getattr(event, "src_path", None),
                getattr(event, "dest_path", None),
            ),
        )


class DebouncedSync:
    """Run a sync after a quiet period and coalesce notifications while it runs."""

    def __init__(
        self,
        request: Callable[[], bool],
        delay: float,
        timer_factory=threading.Timer,
    ) -> None:
        if delay <= 0:
            raise ValueError("delay must be positive")
        self._request = request
        self._delay = delay
        self._timer_factory = timer_factory
        self._condition = threading.Condition()
        self._timer = None
        self._running = False
        self._pending = False
        self._retry_used = False
        self._stopped = False
        self._generation = 0
        self._callback_thread = None

    def start(self) -> None:
        """Keep the debouncer active; provided for lifecycle symmetry."""
        with self._condition:
            if self._stopped:
                return

    def _schedule_locked(self) -> None:
        self._generation += 1
        generation = self._generation
        timer = self._timer_factory(self._delay, lambda: self._fire(generation))
        timer.daemon = True
        self._timer = timer
        timer.start()

    def notify(self) -> None:
        with self._condition:
            if self._stopped:
                return
            self._pending = True
            if not self._running:
                if self._timer is not None:
                    self._timer.cancel()
                else:
                    self._retry_used = False
                self._schedule_locked()

    def _fire(self, generation: int) -> None:
        with self._condition:
            if self._stopped or generation != self._generation:
                return
            self._timer = None
            self._pending = False
            self._running = True
            self._callback_thread = threading.current_thread()

        retry = False
        try:
            retry = not bool(self._request())
        except Exception:
            _LOG.error("Debounced sync request failed")
        finally:
            with self._condition:
                self._running = False
                self._callback_thread = None
                should_retry = retry and not self._retry_used
                if not self._stopped and (self._pending or should_retry):
                    if should_retry:
                        self._retry_used = True
                    self._pending = False
                    self._schedule_locked()
                elif not self._pending:
                    self._retry_used = False
                self._condition.notify_all()

    def stop(self, wait: bool = True) -> None:
        with self._condition:
            if self._stopped:
                running = self._running
            else:
                self._stopped = True
                self._pending = False
                self._generation += 1
                timer = self._timer
                self._timer = None
                if timer is not None:
                    timer.cancel()
                running = self._running

        if wait and running and threading.current_thread() is not self._callback_thread:
            with self._condition:
                while self._running:
                    self._condition.wait()


class DatabaseWatcher:
    """Own a non-recursive watchdog observer for one database directory."""

    def __init__(
        self,
        database_path: Path,
        debounce: DebouncedSync,
        observer_factory=Observer,
    ) -> None:
        self._database_path = _normalize_path(database_path)
        self._debounce = debounce
        self._observer_factory = observer_factory
        self._condition = threading.Condition()
        self._observer = None
        self._observer_start_attempted = False
        self._started = False
        self._starting = False
        self._stopping = False
        self._stop_requested = False

    @staticmethod
    def _cleanup_after_start_failure(observer, start_attempted: bool) -> bool:
        errors = False
        try:
            observer.stop()
        except Exception:
            errors = True
            _LOG.error("Failed to stop database watcher after startup failure")
        if start_attempted:
            try:
                observer.join(timeout=10)
            except Exception:
                errors = True
                _LOG.error("Failed to join database watcher after startup failure")

        try:
            alive = observer.is_alive()
        except Exception:
            errors = True
            alive = True
            _LOG.error("Failed to check database watcher state after startup failure")
        if alive:
            _LOG.error("Database watcher remained alive after startup failure cleanup")
        return not errors and not alive

    def start(self) -> None:
        with self._condition:
            while self._starting or self._stopping:
                self._condition.wait()
            if self._started:
                return
            self._starting = True
            self._stop_requested = False

        parent = self._database_path.parent
        try:
            if not parent.is_dir():
                raise FileNotFoundError(f"Database directory not found: {parent}")
        except Exception:
            with self._condition:
                self._starting = False
                self._stop_requested = False
                self._condition.notify_all()
            raise

        observer = None
        try:
            observer = self._observer_factory()
            with self._condition:
                self._observer = observer
            handler = DatabaseEventFilter(self._database_path, self._debounce.notify)
            # Scheduling is part of startup so a partially configured observer is cleaned up.
            observer.schedule(handler, str(parent), recursive=False)
            # Mark the attempt before calling into watchdog: start() may launch a
            # thread and then raise, so cleanup must still stop, join, and inspect it.
            with self._condition:
                self._observer_start_attempted = True
            observer.start()
        except Exception:
            cleanup_succeeded = (
                observer is None
                or self._cleanup_after_start_failure(
                    observer, self._observer_start_attempted
                )
            )
            with self._condition:
                if cleanup_succeeded:
                    if self._observer is observer:
                        self._observer = None
                    self._observer_start_attempted = False
                    self._started = False
                    self._stop_requested = False
                else:
                    # Keep a live or incompletely cleaned observer available for stop() to retry.
                    self._started = observer is not None
                self._starting = False
                self._condition.notify_all()
            raise

        with self._condition:
            self._started = True
            self._starting = False
            stop_requested = self._stop_requested
            self._condition.notify_all()

        if stop_requested:
            self.stop()

    def stop(self) -> None:
        with self._condition:
            if self._starting:
                self._stop_requested = True
                while self._starting:
                    self._condition.wait()
            while self._stopping:
                self._condition.wait()
                if not self._started:
                    return
            if not self._started:
                return
            observer = self._observer
            start_attempted = self._observer_start_attempted
            self._stopping = True

        errors = []
        try:
            try:
                observer.stop()
            except Exception as exc:
                errors.append(exc)
                _LOG.error("Failed to stop database watcher")
            if start_attempted:
                try:
                    observer.join(timeout=10)
                except Exception as exc:
                    errors.append(exc)
                    _LOG.error("Failed to join database watcher")

            alive = False
            try:
                alive = observer.is_alive()
            except Exception as exc:
                errors.append(exc)
                _LOG.error("Failed to check database watcher state")
            if alive:
                _LOG.error("Database watcher did not stop within 10 seconds")
        finally:
            with self._condition:
                cleanup_succeeded = not errors and not alive
                if cleanup_succeeded:
                    self._started = False
                    self._observer = None
                    self._observer_start_attempted = False
                    self._stop_requested = False
                self._stopping = False
                self._condition.notify_all()

        if errors:
            raise errors[0]
