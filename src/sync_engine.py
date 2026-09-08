"""Coordinate one snapshot-to-Git synchronization transaction."""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Protocol, Tuple

from .filesystem import reconcile
from .models import ChangeSet, RenderedSnapshot, SyncResult, ThingsSnapshot
from .renderer import render_snapshot


_LOG = logging.getLogger(__name__)


class SnapshotReader(Protocol):
    def read_snapshot(self) -> ThingsSnapshot:
        ...


class GitSyncClient(Protocol):
    def sync(
        self,
        changes: ChangeSet,
        auto_commit: bool,
        auto_push: bool,
        remote: str,
        branch: str,
    ) -> Tuple[bool, bool]:
        ...


class SyncEngine:
    def __init__(
        self,
        config,
        reader: SnapshotReader,
        git_client: GitSyncClient,
        renderer: Callable[[ThingsSnapshot], RenderedSnapshot] = render_snapshot,
        reconciler: Callable[[Path, RenderedSnapshot], ChangeSet] = reconcile,
    ) -> None:
        self.config = config
        self.reader = reader
        self.git_client = git_client
        self.renderer = renderer
        self.reconciler = reconciler
        self._lock = threading.Lock()

    def _sync_locked(self, status) -> SyncResult:
        status["stage"] = "reader"
        snapshot = self.reader.read_snapshot()
        status["stage"] = "renderer"
        rendered = self.renderer(snapshot)
        status["stage"] = "reconciler"
        changes = self.reconciler(self.config.repo_path, rendered)
        status["changes"] = changes
        status["stage"] = "git"
        committed, pushed = self.git_client.sync(
            changes,
            auto_commit=self.config.auto_commit,
            auto_push=self.config.auto_push,
            remote=self.config.git_remote,
            branch=self.config.git_branch,
        )
        status["committed"] = committed
        status["pushed"] = pushed
        return SyncResult(changes, committed, pushed)

    @staticmethod
    def _log_sync(started, status) -> None:
        try:
            changes = status["changes"]
            counts = (
                (len(changes.added), len(changes.modified), len(changes.deleted))
                if changes is not None
                else ("unavailable", "unavailable", "unavailable")
            )
            committed = status["committed"]
            pushed = status["pushed"]
            if committed is None:
                committed = "not executed"
            if pushed is None:
                pushed = "not executed"
            duration = time.monotonic() - started
            error = status["error"]
            if error is None:
                _LOG.info(
                    "sync succeeded duration=%.3fs added=%s modified=%s deleted=%s committed=%s pushed=%s",
                    duration,
                    counts[0],
                    counts[1],
                    counts[2],
                    committed,
                    pushed,
                )
            else:
                _LOG.error(
                    "sync failed stage=%s duration=%.3fs added=%s modified=%s deleted=%s committed=%s pushed=%s error=present",
                    status["stage"],
                    duration,
                    counts[0],
                    counts[1],
                    counts[2],
                    committed,
                    pushed,
                )
        except BaseException:
            # Logging must never hide a pipeline exception or prevent unlock.
            pass

    def _run_locked(self, started) -> SyncResult:
        status = {
            "stage": "reader",
            "changes": None,
            "committed": None,
            "pushed": None,
            "error": None,
        }
        try:
            return self._sync_locked(status)
        except BaseException as error:
            status["error"] = error
            raise
        finally:
            try:
                self._log_sync(started, status)
            finally:
                self._lock.release()

    def sync(self) -> SyncResult:
        started = time.monotonic()
        self._lock.acquire()
        return self._run_locked(started)

    def sync_if_idle(self) -> bool:
        started = time.monotonic()
        if not self._lock.acquire(blocking=False):
            return False
        self._run_locked(started)
        return True
