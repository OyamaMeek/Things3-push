"""Read-only adapter for snapshots from the Things Python API."""

import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, Tuple, cast

from .models import ChecklistItem, ContainerSnapshot, TaskSnapshot, ThingsSnapshot

logger = logging.getLogger(__name__)


class ThingsAPI(Protocol):
    def todos(self, **kwargs: object) -> object:
        ...

    def projects(self, **kwargs: object) -> object:
        ...

    def areas(self, **kwargs: object) -> object:
        ...

    def today(self, **kwargs: object) -> object:
        ...

    def upcoming(self, **kwargs: object) -> object:
        ...


MODERN_PATTERN = Path("Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac")
OLD_RELATIVE = MODERN_PATTERN / "Things Database.thingsdatabase/main.sqlite"


def load_default_api() -> ThingsAPI:
    """Load and validate the module-level read-only Things API."""
    import things

    required = ("todos", "projects", "areas", "today", "upcoming")
    missing = [name for name in required if not callable(getattr(things, name, None))]
    if missing:
        raise AttributeError(
            "Things API is missing callable(s): " + ", ".join(missing)
        )
    return cast(ThingsAPI, things)


def discover_database_path(
    explicit: Optional[Path] = None, home: Optional[Path] = None
) -> Path:
    """Find the Things database, preferring an explicitly supplied path."""
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Things database not found: {candidate}")
        return candidate

    home_path = home or Path.home()
    root = home_path / MODERN_PATTERN
    modern = sorted(
        root.glob("ThingsData-*/Things Database.thingsdatabase/main.sqlite")
    )
    if modern:
        return modern[-1].resolve()

    old = (home_path / OLD_RELATIVE).resolve()
    if old.is_file():
        return old
    raise FileNotFoundError("Things database was not found in known locations")


def _text(value: object, default: Optional[str] = None) -> Optional[str]:
    """Return a text value while preserving missing/None optional fields."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _integer(value: object, default: int = 0) -> int:
    """Return an integer value, using a deterministic default when absent."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_checklist(items: object) -> Tuple[ChecklistItem, ...]:
    """Normalize checklist dictionaries and provide stable ordering."""
    if not isinstance(items, (list, tuple)):
        return ()

    normalized: List[ChecklistItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        uuid = _text(item.get("uuid"), "") or ""
        status = _text(item.get("status"), "incomplete") or "incomplete"
        title = _text(item.get("title"), "") or ""
        normalized.append(
            ChecklistItem(
                uuid=uuid,
                title=title,
                status=cast(str, status),
                stop_date=_text(item.get("stop_date")),
                created=_text(item.get("created")),
                modified=_text(item.get("modified")),
            )
        )
    normalized.sort(key=lambda item: (item.created or "", item.uuid))
    return tuple(normalized)


def _normalize_task(row: Dict[str, object]) -> TaskSnapshot:
    """Normalize one Things to-do dictionary into a domain snapshot."""
    status = _text(row.get("status"), "incomplete") or "incomplete"
    tags_value = row.get("tags")
    tags: List[str] = []
    if isinstance(tags_value, (list, tuple, set)):
        tags = [text for text in (_text(tag) for tag in tags_value) if text is not None]
    tags.sort()

    return TaskSnapshot(
        uuid=_text(row.get("uuid"), "") or "",
        title=_text(row.get("title"), "") or "",
        status=cast(str, status),
        task_type=_text(row.get("type"), "to-do") or "to-do",
        start=_text(row.get("start")),
        area_uuid=_text(row.get("area")),
        area_title=_text(row.get("area_title")),
        project_uuid=_text(row.get("project")),
        project_title=_text(row.get("project_title")),
        heading_uuid=_text(row.get("heading")),
        heading_title=_text(row.get("heading_title")),
        notes=_text(row.get("notes")),
        tags=tuple(tags),
        checklist=_normalize_checklist(row.get("checklist")),
        start_date=_text(row.get("start_date")),
        deadline=_text(row.get("deadline")),
        reminder_time=_text(row.get("reminder_time")),
        stop_date=_text(row.get("stop_date")),
        created=_text(row.get("created")),
        modified=_text(row.get("modified")),
        index=_integer(row.get("index")),
        today_index=_integer(row.get("today_index")),
        trashed=bool(row.get("trashed", False)),
    )


def _normalize_project(row: Dict[str, object]) -> ContainerSnapshot:
    """Normalize one Things project dictionary."""
    return ContainerSnapshot(
        uuid=_text(row.get("uuid"), "") or "",
        kind="project",
        title=_text(row.get("title"), "") or "",
        area_uuid=_text(row.get("area")),
        area_title=_text(row.get("area_title")),
        index=_integer(row.get("index")),
        trashed=bool(row.get("trashed", False)),
    )


def _normalize_area(row: Dict[str, object]) -> ContainerSnapshot:
    """Normalize one Things area dictionary."""
    return ContainerSnapshot(
        uuid=_text(row.get("uuid"), "") or "",
        kind="area",
        title=_text(row.get("title"), "") or "",
        index=_integer(row.get("index")),
        trashed=bool(row.get("trashed", False)),
    )


def _rows(value: object) -> List[Dict[str, object]]:
    """Keep only dictionary rows returned by the external API."""
    if not isinstance(value, (list, tuple)):
        return []
    return [row for row in value if isinstance(row, dict)]


def _dynamic_uuids(value: object) -> Tuple[str, ...]:
    """Extract ordered, unique, non-trashed to-do UUIDs."""
    result: List[str] = []
    seen = set()
    for row in _rows(value):
        if row.get("type") != "to-do" or bool(row.get("trashed", False)):
            continue
        uuid = _text(row.get("uuid"))
        if uuid and uuid not in seen:
            seen.add(uuid)
            result.append(uuid)
    return tuple(result)


class ThingsReader:
    """Read a complete, immutable Things snapshot without mutation APIs."""

    def __init__(
        self,
        api: ThingsAPI,
        database_path: Path,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 3,
        retry_delay: float = 10.0,
    ) -> None:
        self.api = api
        self.database_path = database_path
        self.sleep = sleep
        self.attempts = attempts
        self.retry_delay = retry_delay

    def read_snapshot(self) -> ThingsSnapshot:
        for attempt in range(1, self.attempts + 1):
            try:
                return self._read_once()
            except Exception:
                logger.exception(
                    "Things snapshot read failed on attempt %s/%s",
                    attempt,
                    self.attempts,
                )
                if attempt == self.attempts:
                    raise
                self.sleep(self.retry_delay)
        raise AssertionError("unreachable")

    def _read_once(self) -> ThingsSnapshot:
        filepath = str(self.database_path)
        tasks_by_uuid = {}
        for status in ("incomplete", "completed", "canceled"):
            rows = _rows(
                self.api.todos(
                    status=status,
                    trashed=False,
                    context_trashed=False,
                    include_items=True,
                    filepath=filepath,
                )
            )
            for row in rows:
                if row.get("type") != "to-do" or bool(row.get("trashed", False)):
                    continue
                uuid = _text(row.get("uuid"))
                if not uuid:
                    continue
                previous = tasks_by_uuid.get(uuid)
                if previous is not None and previous != row:
                    logger.warning("Conflicting Things payloads for task %s", uuid)
                tasks_by_uuid[uuid] = row

        projects = []
        for row in _rows(self.api.projects(trashed=False, filepath=filepath)):
            if row.get("type") == "project" and not bool(row.get("trashed", False)):
                projects.append(_normalize_project(row))

        areas = []
        for row in _rows(self.api.areas(filepath=filepath)):
            if row.get("type") == "area" and not bool(row.get("trashed", False)):
                areas.append(_normalize_area(row))

        today_uuids = _dynamic_uuids(self.api.today(filepath=filepath))
        upcoming_uuids = _dynamic_uuids(self.api.upcoming(filepath=filepath))

        return ThingsSnapshot(
            tasks=tuple(_normalize_task(row) for row in tasks_by_uuid.values()),
            projects=tuple(projects),
            areas=tuple(areas),
            today_uuids=today_uuids,
            upcoming_uuids=upcoming_uuids,
        )
