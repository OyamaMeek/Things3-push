"""Pure, deterministic rendering of Things snapshots into Markdown documents."""

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .markdown import render_document
from .models import ContainerPath, ContainerSnapshot, RenderedSnapshot, TaskSnapshot, ThingsSnapshot
from .utils import sanitize_path_segment


_LOG = logging.getLogger(__name__)
_ROOT_FILES = (
    (Path("Inbox.md"), "Inbox"),
    (Path("Today.md"), "Today"),
    (Path("Anytime.md"), "Anytime"),
    (Path("Someday.md"), "Someday"),
    (Path("Upcoming.md"), "Upcoming"),
    (Path("已完成.md"), "已完成"),
    (Path("已取消.md"), "已取消"),
)
_CONTAINER_FILES = (
    ("tasks.md", "任务"),
    ("已完成.md", "已完成"),
    ("已取消.md", "已取消"),
)
_VALID_STARTS = {"Inbox", "Anytime", "Someday"}
_MAX_SEGMENT_LENGTH = 120


def _container_sort_key(container: ContainerSnapshot) -> Tuple[str, str]:
    return (container.title.casefold(), container.uuid)


def _suffix_segment(base: str, uuid: str, length: int, ordinal: int = 0) -> str:
    suffix = "-" + uuid[:length]
    if ordinal:
        suffix += "-" + str(ordinal)
    available = _MAX_SEGMENT_LENGTH - len(suffix)
    if available <= 0:
        return suffix[-_MAX_SEGMENT_LENGTH:]
    return base[:available].rstrip(".").strip() + suffix


def _unique_suffix_lengths(containers: Sequence[ContainerSnapshot], bases: Dict[str, str], needs_suffix: Set[str]) -> Dict[str, int]:
    """Return UUID prefix lengths that distinguish suffixed peers."""
    lengths = {container.uuid: min(8, len(container.uuid)) for container in containers if container.uuid in needs_suffix}
    while True:
        groups: Dict[Tuple[str, str], List[ContainerSnapshot]] = {}
        for container in containers:
            if container.uuid not in needs_suffix:
                continue
            key = (bases[container.uuid].casefold(), container.uuid[:lengths[container.uuid]].casefold())
            groups.setdefault(key, []).append(container)
        duplicates = [group for group in groups.values() if len(group) > 1]
        if not duplicates:
            return lengths
        changed = False
        for group in duplicates:
            for container in group:
                current = lengths[container.uuid]
                if current < len(container.uuid):
                    lengths[container.uuid] = current + 1
                    changed = True
        if not changed:
            # UUIDs are unique, so this is defensive only for non-standard inputs.
            return lengths


def _collision_ordinals(
    containers: Sequence[ContainerSnapshot], bases: Dict[str, str], lengths: Dict[str, int], needs_suffix: Set[str]
) -> Dict[str, int]:
    """Assign stable ordinal suffixes to residual case-insensitive collisions."""
    candidates: Dict[str, List[ContainerSnapshot]] = {}
    for container in containers:
        segment = (
            _suffix_segment(bases[container.uuid], container.uuid, lengths[container.uuid])
            if container.uuid in needs_suffix
            else bases[container.uuid]
        )
        candidates.setdefault(segment.casefold(), []).append(container)

    ordinals: Dict[str, int] = {}
    for group in candidates.values():
        if len(group) > 1:
            for ordinal, container in enumerate(sorted(group, key=_container_sort_key), start=1):
                ordinals[container.uuid] = ordinal
    return ordinals


def _allocate_kind(containers: Iterable[ContainerSnapshot], kind: str, root: str) -> List[ContainerPath]:
    active = sorted(
        (container for container in containers if not container.trashed),
        key=_container_sort_key,
    )
    bases = {
        container.uuid: sanitize_path_segment(container.title, "{}-{}".format(kind, container.uuid[:8]))
        for container in active
    }
    needs_suffix: Set[str] = set()

    # A case-insensitive duplicate cannot retain either clean segment.
    by_clean_name: Dict[str, List[ContainerSnapshot]] = {}
    for container in active:
        by_clean_name.setdefault(bases[container.uuid].casefold(), []).append(container)
    for group in by_clean_name.values():
        if len(group) > 1:
            needs_suffix.update(container.uuid for container in group)

    # A generated suffix can naturally be another container title.  Mark every
    # conflicting path for suffixing, then repeat until all candidates are unique.
    while True:
        lengths = _unique_suffix_lengths(active, bases, needs_suffix)
        candidates: Dict[str, List[ContainerSnapshot]] = {}
        for container in active:
            segment = (
                _suffix_segment(bases[container.uuid], container.uuid, lengths[container.uuid])
                if container.uuid in needs_suffix
                else bases[container.uuid]
            )
            candidates.setdefault(segment.casefold(), []).append(container)
        conflicts = [group for group in candidates.values() if len(group) > 1]
        if not conflicts:
            break
        previous_count = len(needs_suffix)
        for group in conflicts:
            needs_suffix.update(container.uuid for container in group)
        if len(needs_suffix) == previous_count:
            break

    ordinals = _collision_ordinals(active, bases, lengths, needs_suffix)
    paths = []
    used_segments: Set[str] = set()
    for container in active:
        if container.uuid in needs_suffix:
            ordinal = ordinals.get(container.uuid, 0)
            segment = _suffix_segment(bases[container.uuid], container.uuid, lengths[container.uuid], ordinal)
            while segment.casefold() in used_segments:
                ordinal += 1
                segment = _suffix_segment(bases[container.uuid], container.uuid, lengths[container.uuid], ordinal)
        else:
            segment = bases[container.uuid]
            ordinal = 0
            while segment.casefold() in used_segments:
                ordinal += 1
                segment = _suffix_segment(bases[container.uuid], container.uuid, len(container.uuid), ordinal)
        used_segments.add(segment.casefold())
        paths.append(ContainerPath(container.uuid, kind, Path(root) / segment))
    return paths


def allocate_container_paths(
    projects: Sequence[ContainerSnapshot], areas: Sequence[ContainerSnapshot]
) -> Tuple[ContainerPath, ...]:
    """Allocate safe relative directories for active projects and areas."""
    paths = _allocate_kind(projects, "project", "Projects")
    paths.extend(_allocate_kind(areas, "area", "Areas"))
    return tuple(sorted(paths, key=lambda item: (item.kind, item.relative_dir.as_posix().casefold(), item.uuid)))


def _primary_sort_key(task: TaskSnapshot) -> Tuple[int, str, str, str]:
    return (task.index, task.created or "", task.title.casefold(), task.uuid)


def _descending_text(value: str) -> str:
    return "".join(chr(0x10FFFF - ord(character)) for character in value)


def _terminal_sort_key(task: TaskSnapshot) -> Tuple[str, int, str, str, str]:
    return (_descending_text(task.stop_date or ""),) + _primary_sort_key(task)


def _document_title(path: Path, suffix: str) -> str:
    if len(path.parts) == 1:
        return suffix
    return " / ".join(path.parts[:-1]) + " / " + suffix


def _primary_file(
    task: TaskSnapshot,
    project_paths: Dict[str, Path],
    area_paths: Dict[str, Path],
) -> Path:
    base = project_paths.get(task.project_uuid or "")
    if base is None:
        base = area_paths.get(task.area_uuid or "")
    if task.status == "completed":
        return base / "已完成.md" if base else Path("已完成.md")
    if task.status == "canceled":
        return base / "已取消.md" if base else Path("已取消.md")
    if base:
        return base / "tasks.md"
    if task.start not in _VALID_STARTS:
        _LOG.warning("Incomplete task %s has invalid or missing start %r; routing to Anytime", task.uuid, task.start)
        return Path("Anytime.md")
    return Path(task.start + ".md")


def _dynamic_tasks(
    uuids: Sequence[str], tasks: Dict[str, TaskSnapshot], warned: Set[str]
) -> List[TaskSnapshot]:
    selected = []
    for uuid in uuids:
        task = tasks.get(uuid)
        if task is None:
            if uuid not in warned:
                _LOG.warning("Dynamic view references missing task UUID %s", uuid)
                warned.add(uuid)
            continue
        selected.append(task)
    return selected


def render_snapshot(snapshot: ThingsSnapshot) -> RenderedSnapshot:
    """Render an immutable, entirely in-memory representation of a snapshot."""
    containers = allocate_container_paths(snapshot.projects, snapshot.areas)
    project_paths = {item.uuid: item.relative_dir for item in containers if item.kind == "project"}
    area_paths = {item.uuid: item.relative_dir for item in containers if item.kind == "area"}
    active_tasks = tuple(task for task in snapshot.tasks if not task.trashed)

    tasks_by_file: Dict[Path, List[TaskSnapshot]] = {path: [] for path, _ in _ROOT_FILES}
    titles: Dict[Path, str] = {path: title for path, title in _ROOT_FILES}
    for container in containers:
        for filename, suffix in _CONTAINER_FILES:
            path = container.relative_dir / filename
            tasks_by_file[path] = []
            titles[path] = _document_title(path, suffix)

    for task in active_tasks:
        tasks_by_file[_primary_file(task, project_paths, area_paths)].append(task)

    for path, tasks in tasks_by_file.items():
        if path.name in {"已完成.md", "已取消.md"}:
            tasks.sort(key=_terminal_sort_key)
        else:
            tasks.sort(key=_primary_sort_key)

    active_by_uuid = {task.uuid: task for task in active_tasks}
    warned_missing: Set[str] = set()
    tasks_by_file[Path("Today.md")] = _dynamic_tasks(snapshot.today_uuids, active_by_uuid, warned_missing)
    tasks_by_file[Path("Upcoming.md")] = _dynamic_tasks(snapshot.upcoming_uuids, active_by_uuid, warned_missing)

    files = {path: render_document(titles[path], tasks) for path, tasks in tasks_by_file.items()}
    return RenderedSnapshot(files=files, containers=containers)
