from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Optional, Tuple

TaskStatus = Literal["incomplete", "completed", "canceled"]
ContainerKind = Literal["project", "area"]
ChangeKind = Literal["added", "modified", "deleted"]
_VALID_STATUSES = {"incomplete", "completed", "canceled"}

@dataclass(frozen=True)
class ChecklistItem:
    uuid: str
    title: str
    status: TaskStatus
    stop_date: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"Unsupported checklist status: {self.status}")

@dataclass(frozen=True)
class TaskSnapshot:
    uuid: str
    title: str
    status: TaskStatus
    task_type: str = "to-do"
    start: Optional[str] = None
    area_uuid: Optional[str] = None
    area_title: Optional[str] = None
    project_uuid: Optional[str] = None
    project_title: Optional[str] = None
    heading_uuid: Optional[str] = None
    heading_title: Optional[str] = None
    notes: Optional[str] = None
    tags: Tuple[str, ...] = field(default_factory=tuple)
    checklist: Tuple[ChecklistItem, ...] = field(default_factory=tuple)
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    reminder_time: Optional[str] = None
    stop_date: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    index: int = 0
    today_index: int = 0
    trashed: bool = False
    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"Unsupported task status: {self.status}")
        if self.task_type != "to-do":
            raise ValueError(f"Unsupported task type: {self.task_type}")
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "checklist", tuple(self.checklist))

@dataclass(frozen=True)
class ContainerSnapshot:
    uuid: str
    kind: ContainerKind
    title: str
    area_uuid: Optional[str] = None
    area_title: Optional[str] = None
    index: int = 0
    trashed: bool = False

@dataclass(frozen=True)
class ThingsSnapshot:
    tasks: Tuple[TaskSnapshot, ...] = field(default_factory=tuple)
    projects: Tuple[ContainerSnapshot, ...] = field(default_factory=tuple)
    areas: Tuple[ContainerSnapshot, ...] = field(default_factory=tuple)
    today_uuids: Tuple[str, ...] = field(default_factory=tuple)
    upcoming_uuids: Tuple[str, ...] = field(default_factory=tuple)
    def __post_init__(self) -> None:
        for name in ("tasks", "projects", "areas", "today_uuids", "upcoming_uuids"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        task_ids = [task.uuid for task in self.tasks]
        container_ids = [c.uuid for c in self.projects + self.areas]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Duplicate task UUID in snapshot")
        if len(container_ids) != len(set(container_ids)):
            raise ValueError("Duplicate container UUID in snapshot")

@dataclass(frozen=True)
class ContainerPath:
    uuid: str
    kind: ContainerKind
    relative_dir: Path

@dataclass(frozen=True)
class RenderedSnapshot:
    files: Mapping[Path, str]
    containers: Tuple[ContainerPath, ...]
    def __post_init__(self) -> None:
        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))
        object.__setattr__(self, "containers", tuple(self.containers))

@dataclass(frozen=True)
class ChangeSet:
    added: Tuple[Path, ...] = field(default_factory=tuple)
    modified: Tuple[Path, ...] = field(default_factory=tuple)
    deleted: Tuple[Path, ...] = field(default_factory=tuple)
    git_paths: Tuple[Path, ...] = field(default_factory=tuple)
    @property
    def paths(self) -> Tuple[Path, ...]:
        return tuple(sorted(set(self.added + self.modified + self.deleted)))
    @property
    def changed(self) -> bool:
        return bool(self.paths)
    def __post_init__(self) -> None:
        for name in ("added", "modified", "deleted"):
            object.__setattr__(self, name, tuple(sorted(set(getattr(self, name)))))
        object.__setattr__(self, "git_paths", tuple(sorted(set(self.git_paths))))
        if not self.git_paths and self.paths:
            object.__setattr__(self, "git_paths", self.paths)

@dataclass(frozen=True)
class SyncResult:
    changes: ChangeSet
    committed: bool = False
    pushed: bool = False
