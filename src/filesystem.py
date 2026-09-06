"""Atomic reconciliation of rendered Things Markdown files."""

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Tuple

from .markdown import GENERATED_MARKER, is_managed_markdown
from .models import ChangeSet, RenderedSnapshot

MANIFEST_PATH = Path(".things3-sync-manifest.json")
_MANIFEST_GENERATOR = "things3-github-sync"
_MANIFEST_VERSION = 1
_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Manifest:
    """Versioned record of files and containers owned by the synchronizer."""

    version: int = _MANIFEST_VERSION
    managed_files: Tuple[Path, ...] = field(default_factory=tuple)
    active_containers: Mapping[str, Path] = field(default_factory=dict)
    archived_containers: Mapping[str, Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "managed_files", tuple(sorted(set(self.managed_files))))
        object.__setattr__(
            self, "active_containers", MappingProxyType(dict(sorted(self.active_containers.items())))
        )
        object.__setattr__(
            self, "archived_containers", MappingProxyType(dict(sorted(self.archived_containers.items())))
        )


def _is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_relative_path(repo_path: Path, relative_path: Path) -> bool:
    """Return whether a POSIX-host relative path stays inside the repository."""
    if not isinstance(relative_path, Path) or not relative_path.parts or relative_path.is_absolute():
        return False
    if ".." in relative_path.parts:
        return False
    root = repo_path.resolve()
    return _is_relative_to((root / relative_path).resolve(), root)


def _require_safe_path(repo_path: Path, relative_path: Path) -> None:
    if not _safe_relative_path(repo_path, relative_path):
        raise ValueError("unsafe repository-relative path: {!s}".format(relative_path))


def _empty_manifest() -> Manifest:
    return Manifest()


def _read_manifest_mapping(repo_path: Path, value: object, name: str) -> Mapping[str, Path]:
    if not isinstance(value, dict):
        raise ValueError("manifest {} must be an object".format(name))
    result = {}
    for key, path in value.items():
        if type(key) is not str or not key or type(path) is not str:
            raise ValueError("manifest {} has invalid entry".format(name))
        relative_path = Path(path)
        _require_safe_path(repo_path, relative_path)
        result[key] = relative_path
    return result


def load_manifest(repo_path: Path) -> Manifest:
    """Safely load the current repository manifest without modifying disk."""
    repo_path = Path(repo_path)
    manifest_path = repo_path / MANIFEST_PATH
    if not manifest_path.exists():
        return _empty_manifest()
    try:
        with manifest_path.open("r", encoding="utf-8") as manifest_file:
            data = json.load(manifest_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid sync manifest") from error
    if not isinstance(data, dict):
        raise ValueError("manifest must be an object")
    expected_keys = {
        "_generated_by",
        "version",
        "managed_files",
        "active_containers",
        "archived_containers",
    }
    if set(data) != expected_keys:
        raise ValueError("manifest does not match the version 1 schema")
    if data.get("_generated_by") != _MANIFEST_GENERATOR:
        raise ValueError("manifest has an invalid generator marker")
    if type(data.get("version")) is not int or data["version"] != _MANIFEST_VERSION:
        raise ValueError("manifest has an unsupported version")
    managed_files = data.get("managed_files")
    if not isinstance(managed_files, list) or not all(type(path) is str for path in managed_files):
        raise ValueError("manifest managed_files must be a list of paths")
    paths = tuple(Path(path) for path in managed_files)
    if len(paths) != len(set(paths)):
        raise ValueError("manifest managed_files contains duplicates")
    for path in paths:
        _require_safe_path(repo_path, path)
    return Manifest(
        managed_files=paths,
        active_containers=_read_manifest_mapping(repo_path, data.get("active_containers"), "active_containers"),
        archived_containers=_read_manifest_mapping(
            repo_path, data.get("archived_containers"), "archived_containers"
        ),
    )


def _manifest_content(manifest: Manifest) -> str:
    data = {
        "_generated_by": _MANIFEST_GENERATOR,
        "version": manifest.version,
        "managed_files": [path.as_posix() for path in manifest.managed_files],
        "active_containers": {
            key: path.as_posix() for key, path in manifest.active_containers.items()
        },
        "archived_containers": {
            key: path.as_posix() for key, path in manifest.archived_containers.items()
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    """Replace a UTF-8 text file atomically with a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=".{}.".format(path.name),
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _remove_empty_container_directories(repo_path: Path, containers: Mapping[str, Path]) -> None:
    root = repo_path.resolve()
    stop_names = {"Projects", "Areas"}
    for relative_dir in set(containers.values()):
        current = repo_path / relative_dir
        while current != repo_path and current.name not in stop_names:
            try:
                current.rmdir()
            except OSError:
                _LOG.warning("Not removing nonempty container directory: %s", relative_dir)
                break
            current = current.parent
        if current.resolve() == root:
            continue


def _container_mapping(repo_path: Path, rendered: RenderedSnapshot) -> Mapping[str, Path]:
    containers = {}
    for container in rendered.containers:
        relative_dir = container.relative_dir
        _require_safe_path(repo_path, relative_dir)
        key = "{}:{}".format(container.kind, container.uuid)
        if key in containers and containers[key] != relative_dir:
            raise ValueError("duplicate container identity: {}".format(key))
        containers[key] = relative_dir
    return containers


def _archive_uuid_suffix(uuid: str) -> str:
    sanitized = "".join(character if character.isalnum() else "-" for character in uuid)
    if any(character.isalnum() for character in sanitized):
        return sanitized[:8]
    return hashlib.sha256(uuid.encode()).hexdigest()[:8]


def _archive_directory(key: str, active_dir: Path) -> Path:
    kind, uuid = key.split(":", 1)
    roots = {"project": "Projects", "area": "Areas"}
    try:
        archive_root = roots[kind]
    except KeyError as error:
        raise ValueError("unsupported container identity: {}".format(key)) from error
    return Path("Archived") / archive_root / "{}-{}".format(active_dir.name, _archive_uuid_suffix(uuid))


def _managed_paths_in_container(managed_files: Tuple[Path, ...], container_dir: Path) -> Tuple[Path, ...]:
    return tuple(path for path in managed_files if _is_relative_to(path, container_dir))


def _archive_path(active_path: Path, active_dir: Path, archive_dir: Path) -> Path:
    return archive_dir / active_path.relative_to(active_dir)


def _preflight_manifest_destination(repo_path: Path) -> None:
    """Reject non-regular manifest entries without following symlinks."""
    manifest_path = repo_path / MANIFEST_PATH
    if not os.path.lexists(str(manifest_path)):
        return
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise FileExistsError("unmanaged destination: {!s}".format(MANIFEST_PATH))


def _preflight_destination(repo_path: Path, relative_path: Path, previous: Manifest) -> None:
    """Ensure every existing destination component is safe before writes begin."""
    destination = repo_path / relative_path
    current = repo_path
    for component in relative_path.parts:
        current = current / component
        if not os.path.lexists(str(current)):
            continue
        if current.is_symlink():
            raise FileExistsError("unmanaged destination: {!s}".format(relative_path))
        if current == destination:
            if not current.is_file():
                raise FileExistsError("unmanaged destination: {!s}".format(relative_path))
            if relative_path in previous.managed_files:
                return
            try:
                managed = is_managed_markdown(_read_text(current))
            except (OSError, UnicodeDecodeError) as error:
                raise FileExistsError("unmanaged destination: {!s}".format(relative_path)) from error
            if not managed:
                raise FileExistsError("unmanaged destination: {!s}".format(relative_path))
            return
        if not current.is_dir():
            raise FileExistsError("unmanaged destination: {!s}".format(relative_path))


def _preflight_archive_destination(repo_path: Path, relative_path: Path, previous: Manifest) -> None:
    """Require retained archive files to remain marked before overwriting them."""
    _preflight_destination(repo_path, relative_path, previous)
    destination = repo_path / relative_path
    if not destination.exists():
        return
    try:
        marked = destination.is_file() and is_managed_markdown(_read_text(destination))
    except (OSError, UnicodeDecodeError) as error:
        raise FileExistsError("unmanaged destination: {!s}".format(relative_path)) from error
    if not marked:
        raise FileExistsError("unmanaged destination: {!s}".format(relative_path))


def reconcile(repo_path: Path, rendered: RenderedSnapshot) -> ChangeSet:
    """Reconcile managed files, preserving unowned paths and writing manifest last."""
    repo_path = Path(repo_path)
    desired = dict(rendered.files)
    for relative_path, content in desired.items():
        if not isinstance(relative_path, Path) or not isinstance(content, str):
            raise ValueError("rendered files must map paths to text")
        _require_safe_path(repo_path, relative_path)
    active_containers = _container_mapping(repo_path, rendered)
    _preflight_manifest_destination(repo_path)
    previous = load_manifest(repo_path)

    archived_containers = dict(previous.archived_containers)
    archive_moves = []
    for key, old_dir in previous.active_containers.items():
        if key in active_containers:
            continue
        archive_dir = archived_containers.get(key, _archive_directory(key, old_dir))
        _require_safe_path(repo_path, archive_dir)
        archived_containers[key] = archive_dir
        for old_path in _managed_paths_in_container(previous.managed_files, old_dir):
            archive_moves.append((old_path, _archive_path(old_path, old_dir, archive_dir)))

    # Complete ownership preflight must finish before the first filesystem mutation.
    for relative_path in sorted(desired):
        _preflight_destination(repo_path, relative_path, previous)
    for _, archive_path in archive_moves:
        _preflight_archive_destination(repo_path, archive_path, previous)

    added = []
    modified = []
    deleted = []
    for relative_path in sorted(desired):
        destination = repo_path / relative_path
        if not destination.exists():
            _atomic_write(destination, desired[relative_path])
            added.append(relative_path)
        elif _read_text(destination) != desired[relative_path]:
            _atomic_write(destination, desired[relative_path])
            modified.append(relative_path)

    archive_paths = set(
        path
        for archive_dir in archived_containers.values()
        for path in previous.managed_files
        if _is_relative_to(path, archive_dir)
    )
    for old_path, archive_path in archive_moves:
        source = repo_path / old_path
        if not source.exists():
            continue
        if not source.is_file() or not is_managed_markdown(_read_text(source)):
            _LOG.warning("Not deleting unmarked file: %s", old_path)
            continue
        content = _read_text(source)
        destination = repo_path / archive_path
        if not destination.exists():
            _atomic_write(destination, content)
            added.append(archive_path)
        elif _read_text(destination) != content:
            _atomic_write(destination, content)
            modified.append(archive_path)
        source.unlink()
        deleted.append(old_path)
        archive_paths.add(archive_path)

    active_previous_paths = set()
    for directory in previous.active_containers.values():
        active_previous_paths.update(_managed_paths_in_container(previous.managed_files, directory))
    stale_paths = set(previous.managed_files) - archive_paths
    for relative_path in sorted(stale_paths):
        if relative_path in desired or relative_path in deleted:
            continue
        stale_path = repo_path / relative_path
        if not stale_path.exists():
            continue
        if stale_path.is_file() and is_managed_markdown(_read_text(stale_path)):
            stale_path.unlink()
            deleted.append(relative_path)
        else:
            _LOG.warning("Not deleting unmarked file: %s", relative_path)
    _remove_empty_container_directories(repo_path, previous.active_containers)

    new_manifest = Manifest(
        managed_files=tuple(sorted(set(desired) | archive_paths)),
        active_containers=active_containers,
        archived_containers=archived_containers,
    )
    manifest_path = repo_path / MANIFEST_PATH
    manifest_content = _manifest_content(new_manifest)
    if not manifest_path.exists():
        _atomic_write(manifest_path, manifest_content)
        added.append(MANIFEST_PATH)
    elif _read_text(manifest_path) != manifest_content:
        _atomic_write(manifest_path, manifest_content)
        modified.append(MANIFEST_PATH)

    git_paths = set(previous.managed_files) | set(new_manifest.managed_files)
    git_paths.add(MANIFEST_PATH)
    git_paths.update(added)
    git_paths.update(modified)
    git_paths.update(deleted)
    return ChangeSet(added=tuple(added), modified=tuple(modified), deleted=tuple(deleted), git_paths=tuple(git_paths))
