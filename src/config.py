import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional

from .utils import parse_bool

@dataclass(frozen=True)
class AppConfig:
    repo_path: Path
    things_db: Optional[Path] = None
    log_level: str = "INFO"
    log_max_bytes: int = 10_485_760
    log_backup_count: int = 5
    watch_debounce_seconds: float = 2.0
    full_sync_interval: float = 3600.0
    auto_commit: bool = True
    auto_push: bool = True
    git_remote: str = "origin"
    git_branch: str = "main"
    git_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None, *, git_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> "AppConfig":
        values = os.environ if env is None else env
        raw_repo = values.get("REPO_PATH", "").strip()
        if not raw_repo: raise ValueError("REPO_PATH is required")
        repo = Path(raw_repo).expanduser().resolve()
        if not repo.exists() or not repo.is_dir(): raise ValueError(f"REPO_PATH must be an existing directory: {repo}")
        def number(name, default, cast=float, positive=False, nonnegative=False):
            try: result = cast(values.get(name, str(default)))
            except (TypeError, ValueError): raise ValueError(f"{name} must be numeric")
            if positive and result <= 0: raise ValueError(f"{name} must be positive")
            if nonnegative and result < 0: raise ValueError(f"{name} must be non-negative")
            return result
        timeout = number("GIT_TIMEOUT_SECONDS", 30.0, float, positive=True)
        level = values.get("LOG_LEVEL", "INFO").strip().upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}: raise ValueError(f"Unsupported log level: {level}")
        auto_commit = parse_bool("AUTO_COMMIT", values.get("AUTO_COMMIT", "true"))
        auto_push = parse_bool("AUTO_PUSH", values.get("AUTO_PUSH", "true"))
        if auto_push and not auto_commit: raise ValueError("AUTO_PUSH requires AUTO_COMMIT")
        result = git_runner(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo, capture_output=True, text=True, timeout=timeout, check=False)
        if result.returncode != 0 or result.stdout.strip() != "true": raise ValueError(f"REPO_PATH must be a Git work tree: {repo}")
        branch_result = git_runner(["git", "branch", "--show-current"], cwd=repo, capture_output=True, text=True, timeout=timeout, check=False)
        branch = branch_result.stdout.strip()
        configured_branch = values.get("GIT_BRANCH", "main").strip()
        if not branch: raise ValueError("GIT_BRANCH cannot be used with detached HEAD")
        if branch != configured_branch: raise ValueError(f"GIT_BRANCH {configured_branch} does not match checked-out branch {branch}")
        things = values.get("THINGSDB", "").strip()
        return cls(repo, Path(things).expanduser().resolve() if things else None, level, number("LOG_MAX_BYTES", 10485760, int, positive=True), number("LOG_BACKUP_COUNT", 5, int, nonnegative=True), number("WATCH_DEBOUNCE_SECONDS", 2.0, float, positive=True), number("FULL_SYNC_INTERVAL", 3600.0, float, positive=True), auto_commit, auto_push, values.get("GIT_REMOTE", "origin"), configured_branch, timeout)
