"""Explicit-path Git operations that preserve unrelated staged changes."""

import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

from .models import ChangeSet


PENDING_PUSH_REF = "refs/things3-sync/pending-push"
_LOG = logging.getLogger(__name__)
_URL_RE = re.compile(r"https?://[^\s'\"<>]+")
_SECRET_VALUE_RE = re.compile(r"(?i)\b(token|auth-token|password)=([^&#\s]+)")
_RENAME_OR_COPY = {"R", "C"}
_COMMIT_NO_DIFF = "no-diff"
_COMMIT_SUCCESS = "commit-success"
_COMMIT_FAILURE = "commit-failure"


@dataclass(frozen=True)
class ChangeCounts:
    added: int
    modified: int
    deleted: int


def generate_commit_message(counts: ChangeCounts, now: datetime) -> str:
    """Build the stable message used for managed sync commits."""
    return "Update: {} | Added {}, Modified {}, Deleted {}".format(
        now.strftime("%Y-%m-%d %H:%M"), counts.added, counts.modified, counts.deleted
    )


def _redact_url(match: re.Match) -> str:
    value = match.group(0)
    parsed = urlsplit(value)
    if "@" not in parsed.netloc:
        return value
    userinfo, host = parsed.netloc.rsplit("@", 1)
    if not userinfo:
        return value
    return urlunsplit((parsed.scheme, "***@" + host, parsed.path, parsed.query, parsed.fragment))


def _redact_credentials(text: str) -> str:
    """Remove credentials from URL userinfo and common credential parameters."""
    redacted = _URL_RE.sub(_redact_url, text)
    return _SECRET_VALUE_RE.sub(lambda match: "{}=***".format(match.group(1)), redacted)


def _path_strings(paths: Sequence[Path]) -> Tuple[str, ...]:
    return tuple(sorted({Path(path).as_posix() for path in paths}))


def _counts_from_name_status(output: str) -> ChangeCounts:
    fields = output.split("\0")
    index = 0
    added = modified = deleted = 0
    while index < len(fields):
        status = fields[index]
        if not status:
            break
        index += 1
        code = status[0]
        if code in _RENAME_OR_COPY:
            index += 2
        else:
            index += 1
        if code == "A":
            added += 1
        elif code == "D":
            deleted += 1
        else:
            modified += 1
    return ChangeCounts(added, modified, deleted)


class GitClient:
    """Run narrowly scoped Git commands against one configured repository."""

    def __init__(
        self,
        repo_path: Path,
        timeout: float = 30.0,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.timeout = timeout
        self.runner = runner
        self._commit_state = _COMMIT_NO_DIFF

    def _run(
        self, args: Sequence[str], env: Optional[Mapping[str, str]] = None
    ) -> Optional[subprocess.CompletedProcess]:
        command = ["git"] + list(args)
        kwargs = {
            "cwd": self.repo_path,
            "capture_output": True,
            "text": True,
            "timeout": self.timeout,
            "check": False,
        }
        if env is not None:
            command_env = os.environ.copy()
            command_env.update(env)
            kwargs["env"] = command_env
        try:
            result = self.runner(command, **kwargs)
        except subprocess.TimeoutExpired:
            _LOG.error("Git command timed out: %s", _redact_credentials(" ".join(command)))
            return None
        except OSError as error:
            _LOG.error("Git command failed to start: %s (%s)", _redact_credentials(" ".join(command)), _redact_credentials(str(error)))
            return None
        if result.returncode != 0 and not (
            args[:3] == ["diff", "--cached", "--quiet"] and result.returncode == 1
        ) and not (
            args[:3] == ["show-ref", "--verify", "--quiet"] and result.returncode == 1
        ):
            _LOG.error(
                "Git command failed (%s): %s",
                _redact_credentials(" ".join(command)),
                _redact_credentials(result.stderr or ""),
            )
        return result

    def stage(self, paths: Sequence[Path], *, env: Optional[Mapping[str, str]] = None) -> bool:
        """Stage only the supplied paths and report whether they have a staged diff."""
        pathspecs = _path_strings(paths)
        if not pathspecs:
            return False
        staged = self._run(["add", "--"] + list(pathspecs), env)
        if staged is None or staged.returncode != 0:
            return False
        diff = self._run(["diff", "--cached", "--quiet", "--"] + list(pathspecs), env)
        if diff is None:
            return False
        if diff.returncode == 1:
            return True
        if diff.returncode == 0:
            return False
        return False

    def _isolated_commit(self, paths: Sequence[Path], now: Optional[datetime]) -> bool:
        self._commit_state = _COMMIT_FAILURE
        pathspecs = _path_strings(paths)
        if not pathspecs:
            self._commit_state = _COMMIT_NO_DIFF
            return False
        try:
            descriptor, index_name = tempfile.mkstemp(prefix="things3-sync-index-")
        except OSError as error:
            _LOG.error("Could not initialize temporary Git index: %s", error)
            return False
        os.close(descriptor)
        index_path = Path(index_name)
        try:
            index_path.unlink()
            index_env = {"GIT_INDEX_FILE": str(index_path)}
            seeded = self._run(["read-tree", "HEAD"], index_env)
            if seeded is None or seeded.returncode != 0:
                return False
            staged = self._run(["add", "--"] + list(pathspecs), index_env)
            if staged is None or staged.returncode != 0:
                return False
            diff = self._run(["diff", "--cached", "--quiet", "--"] + list(pathspecs), index_env)
            if diff is None:
                return False
            if diff.returncode == 0:
                self._commit_state = _COMMIT_NO_DIFF
                return False
            if diff.returncode != 1:
                return False
            name_status = self._run(["diff", "--cached", "--name-status", "-z", "--"] + list(pathspecs), index_env)
            if name_status is None or name_status.returncode != 0:
                return False
            counts = _counts_from_name_status(name_status.stdout)
            message = generate_commit_message(counts, now or datetime.now())
            committed = self._run(["commit", "-m", message], index_env)
            if committed is None or committed.returncode != 0:
                return False
        finally:
            try:
                index_path.unlink()
            except FileNotFoundError:
                pass

        refreshed = self._run(["reset", "-q", "HEAD", "--"] + list(pathspecs))
        if refreshed is None or refreshed.returncode != 0:
            _LOG.error("Managed paths committed but real-index refresh failed")
            return False
        self._commit_state = _COMMIT_SUCCESS
        return True

    def commit(self, changes: ChangeSet, paths: Sequence[Path], now: Optional[datetime] = None) -> bool:
        """Commit managed paths through an isolated temporary index."""
        del changes
        return self._isolated_commit(paths, now)

    def push(self, remote: str, branch: str) -> bool:
        result = self._run(["push", remote, branch])
        return result is not None and result.returncode == 0

    def pending_push(self) -> bool:
        result = self._run(["show-ref", "--verify", "--quiet", PENDING_PUSH_REF])
        if result is None:
            return False
        if result.returncode == 0:
            return True
        if result.returncode != 1:
            _LOG.error("Could not determine pending push state")
        return False

    def _mark_pending_push(self) -> bool:
        result = self._run(["update-ref", PENDING_PUSH_REF, "HEAD"])
        return result is not None and result.returncode == 0

    def _clear_pending_push(self) -> bool:
        result = self._run(["update-ref", "-d", PENDING_PUSH_REF])
        return result is not None and result.returncode == 0

    def sync(
        self,
        changes: ChangeSet,
        auto_commit: bool,
        auto_push: bool,
        remote: str,
        branch: str,
        now: Optional[datetime] = None,
    ) -> Tuple[bool, bool]:
        """Commit managed changes and push only a durably marked sync commit."""
        if auto_push and not auto_commit:
            raise ValueError("AUTO_PUSH requires AUTO_COMMIT")
        if not auto_commit:
            return (False, False)

        paths = changes.git_paths
        committed = False
        pending = False
        if paths:
            committed = self.commit(changes, paths, now)
            if self._commit_state == _COMMIT_FAILURE:
                return (False, False)
            if committed:
                if not self._mark_pending_push():
                    return (False, False)
                pending = True
        if not pending and auto_push:
            pending = self.pending_push()
        if not auto_push or not pending:
            return (committed, False)
        if not self.push(remote, branch):
            return (committed, False)
        if not self._clear_pending_push():
            _LOG.error("Push succeeded but pending push reference could not be deleted")
            return (committed, False)
        return (committed, True)
