"""Interactively create a local configuration file for the sync service."""

import argparse
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def dotenv_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'


def validate_repository(path: Path, *, git_runner=subprocess.run) -> Path:
    repo = path.expanduser().resolve()
    if not repo.is_dir():
        raise ValueError("Repository path must be an existing directory")
    result = git_runner(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise ValueError("Repository path must be a Git work tree")
    return repo


def write_env(repo_path: Path, destination: Path, *, auto_push: bool, overwrite: bool = False) -> None:
    destination = destination.resolve()
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    content = "\n".join((
        f"REPO_PATH={dotenv_quote(str(repo_path.expanduser().resolve()))}",
        "LOG_LEVEL=INFO", "LOG_MAX_BYTES=10485760", "LOG_BACKUP_COUNT=5",
        "WATCH_DEBOUNCE_SECONDS=2", "FULL_SYNC_INTERVAL=3600", "AUTO_COMMIT=true",
        f"AUTO_PUSH={'true' if auto_push else 'false'}", "GIT_REMOTE=origin", "GIT_BRANCH=main",
        "GIT_TIMEOUT_SECONDS=30", "",
    ))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        if overwrite:
            os.replace(temporary, destination)
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError:
                raise FileExistsError(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main(*, input_fn=input, output_fn=print, git_runner=subprocess.run, project_dir: Optional[Path] = None) -> int:
    project = (project_dir or Path(__file__).resolve().parent).resolve()
    destination = project / ".env"
    if destination.exists():
        output_fn(f"Configuration already exists: {destination}")
        return 1
    try:
        repo = validate_repository(Path(input_fn("Local Git repository path: ").strip()), git_runner=git_runner)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        output_fn("Repository validation failed")
        return 1
    auto_push = input_fn("Enable automatic push? [Y/n]: ").strip().lower() not in {"n", "no"}
    try:
        write_env(repo, destination, auto_push=auto_push)
    except FileExistsError:
        output_fn(f"Configuration already exists: {destination}")
        return 1
    output_fn(f"Configuration written: {destination}")
    output_fn(f"Next: {shlex.quote(os.sys.executable)} {shlex.quote(str(project / 'main.py'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
