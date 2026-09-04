# Things3 到 GitHub Markdown 同步 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 macOS 后台服务，只读监听 Things3 数据库，把完整任务快照确定性导出为 Markdown，并按配置自动提交和推送到 Git 仓库。

**Architecture:** 所有触发源都调用同一条快照流水线：只读适配器规范化 Things 字典，纯渲染器生成期望文件和容器映射，文件协调器原子收敛磁盘状态，Git 层只暂存明确路径。服务层用防抖队列串行化数据库事件、启动同步和定时同步，并在信号退出时等待当前操作结束。

**Tech Stack:** Python 3.9+、`things.py>=1.0.1,<2`、`watchdog>=2.1,<7`、`python-dotenv>=0.19,<2`、标准库 `dataclasses`/`pathlib`/`sqlite3`/`subprocess`/`threading`/`logging`、pytest。

## Global Constraints

- 运行平台为 macOS，Python 最低版本为 3.9。
- 运行时依赖必须限定为 `things.py>=1.0.1,<2`、`watchdog>=2.1,<7`、`python-dotenv>=0.19,<2`；测试依赖在 `requirements-dev.txt` 中声明。
- Things 数据库只能通过读取接口访问；业务代码不得导入或调用 `complete()`，不得构造 `update` 或 `update-project` URL。
- 所有文件路径使用 `pathlib.Path`；所有 Git 命令使用带超时的 `subprocess.run()`。
- 数据库读取失败后间隔 10 秒重试，最多 3 次；完整快照成功前不得修改目标仓库。
- 禁止使用 `git add .`；只暂存文件协调器返回的明确相对路径。
- 同步器只删除带生成标识的已知托管文件；陌生文件必须保留并记录警告。
- `AUTO_PUSH=true` 必须同时满足 `AUTO_COMMIT=true`。
- 不自动 pull、merge、rebase 或解决远端冲突。
- 输出中不包含参考库未公开的优先级、Evening、附件或重复规则字段。
- 现有 `.gitignore` 和 `docs/CHANGELOG.md` 是用户在本计划开始前已暂存的改动。每个实施提交必须使用 `git commit --only -- <本任务文件>`，不得修改或把它们带入功能提交。
- 本地 `things.py/` 已被忽略，只作为 API 源码和 SQLite 测试 fixture 参考，不作为主项目源码提交。

## File Map

### Runtime package

- `src/__init__.py`：包版本。
- `src/models.py`：不可变快照模型、状态和容器类型。
- `src/config.py`：环境配置解析、校验及 Git 工作树检查。
- `src/utils.py`：日志初始化、布尔/数值配置解析和安全路径段处理。
- `src/things_adapter.py`：数据库路径发现、只读 API 协议、重试和字典规范化。
- `src/markdown.py`：单任务 Markdown 转义与渲染，不处理路由。
- `src/renderer.py`：任务路由、容器路径冲突消解、稳定排序和完整文件集合渲染。
- `src/filesystem.py`：manifest、原子写入、托管文件协调、容器重命名和归档。
- `src/git_ops.py`：明确 pathspec 暂存、差异检测、提交与推送。
- `src/sync_engine.py`：一次同步的事务边界和串行锁。
- `src/watcher.py`：SQLite/WAL/SHM 事件过滤、防抖和补跑调度。
- `src/service.py`：启动同步、周期同步和协调关闭。
- `main.py`：生产入口与信号处理。
- `setup.py`：交互式生成 `.env`。
- `generate_launchd.py`：在项目内生成 launchd plist 预览。

### Configuration and documentation

- `.env.example`：完整配置模板。
- `requirements.txt`：运行时依赖。
- `requirements-dev.txt`：pytest 与覆盖率依赖。
- `README.md`：安装、配置、运行、部署、输出和故障排查。
- `Agent.md`：按真实 API 和最终 MVP 行为修正文档并标记完成项。

### Tests

- `tests/conftest.py`：共享模型工厂和测试路径 fixture。
- `tests/test_config.py`：配置默认值和约束。
- `tests/test_models.py`：模型不变量。
- `tests/test_things_adapter.py`：API 规范化、数据库发现与重试。
- `tests/test_markdown.py`：Markdown 合同。
- `tests/test_renderer.py`：路径分配、主位置、派生视图和确定性。
- `tests/test_filesystem.py`：原子协调、manifest、删除保护和归档。
- `tests/test_git_ops.py`：Git 命令和失败分支。
- `tests/test_sync_engine.py`：流水线边界、无变化和 Git 策略。
- `tests/test_watcher.py`：事件过滤、防抖、同步期间补跑。
- `tests/test_service.py`：启动、周期和优雅退出。
- `tests/test_cli_tools.py`：`.env` 初始化和 plist 生成。
- `tests/test_integration.py`：测试数据库到临时 Git 仓库的端到端验收。

---

### Task 1: Project Foundation, Models, and Configuration

**Files:**
- Create: `src/__init__.py`
- Create: `src/models.py`
- Create: `src/config.py`
- Create: `src/utils.py`
- Create: `.env.example`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: no runtime interfaces from earlier tasks.
- Produces: `ChecklistItem`, `TaskSnapshot`, `ContainerSnapshot`, `ThingsSnapshot`, `ContainerPath`, `RenderedSnapshot`, `ChangeSet`, `SyncResult`; `AppConfig.from_env(env: Optional[Mapping[str, str]] = None, *, git_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> AppConfig`; `setup_logging(log_dir: Path, level: str, max_bytes: int, backup_count: int) -> None`; `sanitize_path_segment(title: str, fallback: str, max_length: int = 120) -> str`.

- [ ] **Step 1: Declare runtime and test dependencies**

Create `requirements.txt` exactly as:

```text
things.py>=1.0.1,<2
watchdog>=2.1,<7
python-dotenv>=0.19,<2
```

Create `requirements-dev.txt` exactly as:

```text
-r requirements.txt
pytest>=8,<9
pytest-cov>=5,<7
```

Create `.env.example` with non-user-specific values:

```dotenv
REPO_PATH=/path/to/your/things-backup-repository
# THINGSDB=/path/to/Things Database.thingsdatabase/main.sqlite
LOG_LEVEL=INFO
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
WATCH_DEBOUNCE_SECONDS=2
FULL_SYNC_INTERVAL=3600
AUTO_COMMIT=true
AUTO_PUSH=true
GIT_REMOTE=origin
GIT_BRANCH=main
GIT_TIMEOUT_SECONDS=30
```

- [ ] **Step 2: Write failing model tests**

Create `tests/test_models.py`:

```python
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.models import ChecklistItem, RenderedSnapshot, TaskSnapshot, ThingsSnapshot


def test_task_snapshot_is_immutable_and_normalizes_collections():
    task = TaskSnapshot(
        uuid="TASK-1",
        title="Ship release",
        status="incomplete",
        tags=("work",),
        checklist=(
            ChecklistItem(uuid="ITEM-1", title="Tag", status="completed"),
        ),
    )

    assert task.tags == ("work",)
    assert task.checklist[0].status == "completed"
    with pytest.raises(FrozenInstanceError):
        task.title = "changed"


def test_task_snapshot_rejects_unknown_status():
    with pytest.raises(ValueError, match="Unsupported task status"):
        TaskSnapshot(uuid="TASK-1", title="x", status="blocked")


def test_rendered_snapshot_copies_files_into_a_read_only_mapping():
    source = {Path("Inbox.md"): "content"}
    rendered = RenderedSnapshot(source, ())
    source[Path("Today.md")] = "later mutation"

    assert dict(rendered.files) == {Path("Inbox.md"): "content"}
    with pytest.raises(TypeError):
        rendered.files[Path("Inbox.md")] = "changed"


def test_snapshot_rejects_duplicate_task_uuids():
    one = TaskSnapshot(uuid="TASK-1", title="one", status="incomplete")
    duplicate = TaskSnapshot(uuid="TASK-1", title="two", status="completed")

    with pytest.raises(ValueError, match="Duplicate task UUID"):
        ThingsSnapshot(tasks=(one, duplicate))
```

- [ ] **Step 3: Run model tests and verify the import failure**

Run:

```bash
python3 -m pytest tests/test_models.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'src'`.

- [ ] **Step 4: Implement immutable domain models**

Create `src/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/models.py` with these exact public fields and validation rules:

```python
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
        object.__setattr__(self, "tasks", tuple(self.tasks))
        object.__setattr__(self, "projects", tuple(self.projects))
        object.__setattr__(self, "areas", tuple(self.areas))
        object.__setattr__(self, "today_uuids", tuple(self.today_uuids))
        object.__setattr__(self, "upcoming_uuids", tuple(self.upcoming_uuids))
        task_ids = [task.uuid for task in self.tasks]
        container_ids = [container.uuid for container in self.projects + self.areas]
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
        object.__setattr__(self, "added", tuple(sorted(set(self.added))))
        object.__setattr__(self, "modified", tuple(sorted(set(self.modified))))
        object.__setattr__(self, "deleted", tuple(sorted(set(self.deleted))))
        if self.git_paths:
            object.__setattr__(self, "git_paths", tuple(sorted(set(self.git_paths))))
        elif self.paths:
            object.__setattr__(self, "git_paths", self.paths)


@dataclass(frozen=True)
class SyncResult:
    changes: ChangeSet
    committed: bool = False
    pushed: bool = False
```

Every snapshot `__post_init__` must normalize externally supplied lists to tuples. `RenderedSnapshot` must copy `files` and wrap that copy in `MappingProxyType`; a frozen dataclass alone does not prevent a caller from mutating a supplied dict. `ThingsSnapshot` rejects duplicate container UUIDs across projects and areas as well as duplicate task UUIDs. `ChangeSet.__post_init__` must normalize all explicit path sequences to sorted unique tuples and derive `git_paths` from `paths` only when no historical pathspec was supplied.

- [ ] **Step 5: Run model tests and verify they pass**

Run:

```bash
python3 -m pytest tests/test_models.py -v
```

Expected: 4 tests pass.

- [ ] **Step 6: Write failing configuration and utility tests**

Create `tests/test_config.py`:

```python
from pathlib import Path
from typing import Dict
from unittest.mock import Mock

import pytest

from src.config import AppConfig
from src.utils import sanitize_path_segment


def valid_env(repo: Path) -> Dict[str, str]:
    return {
        "REPO_PATH": str(repo),
        "AUTO_COMMIT": "true",
        "AUTO_PUSH": "false",
    }


def test_config_applies_documented_defaults(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def runner(command, **kwargs):
        stdout = "true\n" if command[1] == "rev-parse" else "main\n"
        return Mock(returncode=0, stdout=stdout, stderr="")

    runner = Mock(side_effect=runner)
    config = AppConfig.from_env(valid_env(repo), git_runner=runner)

    assert config.repo_path == repo.resolve()
    assert config.watch_debounce_seconds == 2.0
    assert config.full_sync_interval == 3600.0
    assert config.git_timeout_seconds == 30.0
    assert config.git_remote == "origin"
    assert config.git_branch == "main"
    assert runner.call_count == 2


def test_config_rejects_push_without_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = valid_env(repo) | {"AUTO_COMMIT": "false", "AUTO_PUSH": "true"}

    with pytest.raises(ValueError, match="AUTO_PUSH requires AUTO_COMMIT"):
        AppConfig.from_env(env, git_runner=Mock())


def test_config_rejects_non_git_directory(tmp_path):
    runner = Mock(return_value=Mock(returncode=128, stdout="", stderr="not a git repository"))

    with pytest.raises(ValueError, match="Git work tree"):
        AppConfig.from_env(valid_env(tmp_path), git_runner=runner)


def test_config_rejects_checked_out_branch_mismatch(tmp_path):
    runner = Mock(side_effect=[
        Mock(returncode=0, stdout="true\n", stderr=""),
        Mock(returncode=0, stdout="feature\n", stderr=""),
    ])

    with pytest.raises(ValueError, match="GIT_BRANCH main.*feature"):
        AppConfig.from_env(valid_env(tmp_path), git_runner=runner)


def test_sanitize_path_segment_handles_invalid_and_empty_titles():
    assert sanitize_path_segment('  A/B:*?<>|".  ', "project-abc") == "A-B-------"
    assert sanitize_path_segment(" ... ", "project-abc") == "project-abc"
```

- [ ] **Step 7: Run configuration tests and verify missing interfaces**

Run:

```bash
python3 -m pytest tests/test_config.py -v
```

Expected: collection fails because `src.config` and `src.utils` do not exist.

- [ ] **Step 8: Implement utility and configuration parsing**

Create `src/utils.py` with:

```python
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_INVALID_PATH_CHARS = re.compile(r'[/:?*<>|"\x00-\x1f]')


def parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def sanitize_path_segment(title: str, fallback: str, max_length: int = 120) -> str:
    value = _INVALID_PATH_CHARS.sub("-", title).strip().rstrip(".").strip()
    value = value or fallback
    return value[:max_length].rstrip(".").strip() or fallback[:max_length]


def setup_logging(log_dir: Path, level: str, max_bytes: int, backup_count: int) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_dir / "sync.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    stream_handler = logging.StreamHandler()
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=[file_handler, stream_handler],
        force=True,
    )
```

Create `src/config.py` as a frozen dataclass. Its `from_env` method must accept an injectable `git_runner` defaulting to `subprocess.run`, load `os.environ` when `env` is omitted, resolve paths, parse numeric values with positive-range checks, and verify the repository using:

```python
result = git_runner(
    ["git", "rev-parse", "--is-inside-work-tree"],
    cwd=repo_path,
    capture_output=True,
    text=True,
    timeout=30,
    check=False,
)
if result.returncode != 0 or result.stdout.strip() != "true":
    raise ValueError(f"REPO_PATH must be a Git work tree: {repo_path}")
```

Expose these fields with these defaults:

```python
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
```

Reject missing `REPO_PATH`, a nonexistent path, unsupported log levels, non-positive timing values, negative backup counts, and push without commit. After verifying the work tree, run `git branch --show-current`; reject an empty result (detached HEAD) and reject a branch unequal to `GIT_BRANCH`. This guarantees commits and `git push <remote> <branch>` address the same branch. Apply the configured Git timeout to both validation commands and do not log the environment mapping.

- [ ] **Step 9: Run foundation tests**

Run:

```bash
python3 -m pytest tests/test_models.py tests/test_config.py -v
```

Expected: all tests pass.

- [ ] **Step 10: Commit only Task 1 files**

Run:

```bash
git add -- src/__init__.py src/models.py src/config.py src/utils.py .env.example requirements.txt requirements-dev.txt tests/__init__.py tests/test_models.py tests/test_config.py
```

Then commit without consuming the user's pre-staged files:

```bash
git commit --only -m $'feat: add sync models and configuration\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/__init__.py src/models.py src/config.py src/utils.py .env.example requirements.txt requirements-dev.txt tests/__init__.py tests/test_models.py tests/test_config.py
```

Expected: the commit contains exactly the listed Task 1 files; `git status --short` still shows `.gitignore` and `docs/CHANGELOG.md` staged.

---

### Task 2: Read-Only Things Adapter

**Files:**
- Create: `src/things_adapter.py`
- Create: `tests/test_things_adapter.py`

**Interfaces:**
- Consumes: model constructors from `src.models`; optional `AppConfig.things_db`.
- Produces: `ThingsReader(api: ThingsAPI, database_path: Path, sleep: Callable[[float], None] = time.sleep, attempts: int = 3, retry_delay: float = 10.0)`; `ThingsReader.read_snapshot() -> ThingsSnapshot`; `discover_database_path(explicit: Optional[Path] = None, home: Optional[Path] = None) -> Path`; `load_default_api() -> ThingsAPI`.

- [ ] **Step 1: Write adapter normalization and retry tests**

Create `tests/test_things_adapter.py` with a fake read-only API:

```python
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.things_adapter import ThingsReader, discover_database_path


class FakeAPI:
    def todos(self, **kwargs):
        status = kwargs["status"]
        if status == "incomplete":
            return [{
                "uuid": "TASK-1",
                "type": "to-do",
                "title": "Write notes",
                "status": "incomplete",
                "project": "PROJECT-1",
                "project_title": "Release",
                "area": "AREA-1",
                "area_title": "Work",
                "tags": ["important", "work"],
                "checklist": [{
                    "uuid": "ITEM-1",
                    "type": "checklist-item",
                    "title": "Review",
                    "status": "completed",
                }],
                "index": 4,
                "today_index": 2,
            }]
        return []

    def projects(self, **kwargs):
        return [{
            "uuid": "PROJECT-1",
            "type": "project",
            "title": "Release",
            "status": "incomplete",
            "area": "AREA-1",
            "area_title": "Work",
            "index": 1,
        }]

    def areas(self, **kwargs):
        return [{"uuid": "AREA-1", "type": "area", "title": "Work"}]

    def today(self, **kwargs):
        return [{"uuid": "TASK-1", "type": "to-do"}]

    def upcoming(self, **kwargs):
        return []


def test_reader_normalizes_sparse_dictionaries(tmp_path):
    reader = ThingsReader(FakeAPI(), tmp_path / "main.sqlite", sleep=Mock())

    snapshot = reader.read_snapshot()

    task = snapshot.tasks[0]
    assert task.project_uuid == "PROJECT-1"
    assert task.tags == ("important", "work")
    assert task.checklist[0].uuid == "ITEM-1"
    assert snapshot.today_uuids == ("TASK-1",)
    assert snapshot.projects[0].area_uuid == "AREA-1"


def test_reader_deduplicates_status_queries_by_uuid(tmp_path):
    api = FakeAPI()
    api.todos = Mock(side_effect=[
        [{"uuid": "TASK-1", "type": "to-do", "title": "x", "status": "incomplete"}],
        [{"uuid": "TASK-1", "type": "to-do", "title": "x", "status": "completed"}],
        [],
    ])
    reader = ThingsReader(api, tmp_path / "main.sqlite", sleep=Mock())

    snapshot = reader.read_snapshot()

    assert len(snapshot.tasks) == 1
    assert snapshot.tasks[0].status == "completed"


def test_reader_retries_whole_snapshot_three_times(tmp_path):
    api = FakeAPI()
    api.todos = Mock(side_effect=[OSError("locked"), OSError("locked"), [] , [], []])
    sleep = Mock()
    reader = ThingsReader(api, tmp_path / "main.sqlite", sleep=sleep)

    snapshot = reader.read_snapshot()

    assert snapshot.tasks == ()
    assert sleep.call_args_list == [((10.0,),), ((10.0,),)]


def test_reader_raises_after_final_failure_without_extra_sleep(tmp_path):
    api = FakeAPI()
    api.todos = Mock(side_effect=OSError("locked"))
    sleep = Mock()
    reader = ThingsReader(api, tmp_path / "main.sqlite", sleep=sleep)

    with pytest.raises(OSError, match="locked"):
        reader.read_snapshot()

    assert sleep.call_count == 2
```

For database discovery, add tests that construct:

```python
def test_discover_database_prefers_explicit_path(tmp_path):
    database = tmp_path / "main.sqlite"
    database.touch()
    assert discover_database_path(database, home=tmp_path) == database.resolve()


def test_discover_database_prefers_modern_thingsdata_directory(tmp_path):
    modern = tmp_path / "Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-ABC/Things Database.thingsdatabase/main.sqlite"
    modern.parent.mkdir(parents=True)
    modern.touch()
    assert discover_database_path(home=tmp_path) == modern.resolve()
```

- [ ] **Step 2: Run adapter tests and verify missing module**

Run:

```bash
python3 -m pytest tests/test_things_adapter.py -v
```

Expected: collection fails because `src.things_adapter` does not exist.

- [ ] **Step 3: Implement a narrow read-only API protocol and path discovery**

Create `src/things_adapter.py`. Define a `ThingsAPI` protocol containing only:

```python
class ThingsAPI(Protocol):
    def todos(self, **kwargs: object) -> object: ...
    def projects(self, **kwargs: object) -> object: ...
    def areas(self, **kwargs: object) -> object: ...
    def today(self, **kwargs: object) -> object: ...
    def upcoming(self, **kwargs: object) -> object: ...
```

`load_default_api()` imports the module itself, verifies these five callables, and returns it:

```python
def load_default_api() -> ThingsAPI:
    import things
    return cast(ThingsAPI, things)
```

Do not import individual symbols from `things`, especially URL or mutation helpers.

Implement database discovery with exact order:

```python
MODERN_PATTERN = Path("Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac")
OLD_RELATIVE = MODERN_PATTERN / "Things Database.thingsdatabase/main.sqlite"


def discover_database_path(explicit=None, home=None):
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Things database not found: {candidate}")
        return candidate
    root = (home or Path.home()) / MODERN_PATTERN
    modern = sorted(root.glob("ThingsData-*/Things Database.thingsdatabase/main.sqlite"))
    if modern:
        return modern[-1].resolve()
    old = ((home or Path.home()) / OLD_RELATIVE).resolve()
    if old.is_file():
        return old
    raise FileNotFoundError("Things database was not found in known locations")
```

- [ ] **Step 4: Implement sparse-dictionary normalization**

Implement private helpers `_text`, `_integer`, `_normalize_checklist`, `_normalize_task`, `_normalize_project`, and `_normalize_area`. Use `.get()` for every optional external key. Sort tags lexicographically and checklist items by `(created or "", uuid)` for deterministic output.

Status queries must be explicit and pass `filepath=str(database_path)` plus `include_items=True`:

```python
for status in ("incomplete", "completed", "canceled"):
    rows = self.api.todos(
        status=status,
        trashed=False,
        context_trashed=False,
        include_items=True,
        filepath=str(self.database_path),
    )
```

If the same UUID occurs more than once, later terminal-state rows replace earlier rows; log a warning when payloads differ. Filter out rows whose type is not `to-do` or whose `trashed` value is true.

Read projects using `projects(trashed=False, filepath=...)` so completed/canceled but still-present Project containers keep their task-specific export paths; areas use `areas(filepath=...)`, Today uses `today(filepath=...)`, and Upcoming uses `upcoming(filepath=...)`. Dynamic UUID tuples retain API order while dropping duplicates and non-to-do rows.

`read_snapshot()` wraps the entire private `_read_once()` operation in this retry shape:

```python
for attempt in range(1, self.attempts + 1):
    try:
        return self._read_once()
    except Exception:
        logger.exception("Things snapshot read failed on attempt %s/%s", attempt, self.attempts)
        if attempt == self.attempts:
            raise
        self.sleep(self.retry_delay)
raise AssertionError("unreachable")
```

Every API call receives the same explicit `filepath`, so production and fixture behavior are unambiguous.

- [ ] **Step 5: Run adapter tests**

Run:

```bash
python3 -m pytest tests/test_things_adapter.py -v
```

Expected: all fake-API tests pass.

- [ ] **Step 6: Add a fixture-backed compatibility test**

Add a test guarded by the local fixture path:

```python
def test_embedded_things_fixture_is_readable():
    fixture = Path(__file__).parents[1] / "things.py/tests/main.sqlite"
    if not fixture.exists():
        pytest.skip("local things.py fixture is not available")

    reader = ThingsReader(load_default_api(), fixture, sleep=Mock())
    snapshot = reader.read_snapshot()

    assert snapshot.tasks
    assert all(task.task_type == "to-do" for task in snapshot.tasks)
    assert {task.status for task in snapshot.tasks} <= {
        "incomplete", "completed", "canceled"
    }
```

Run:

```bash
PYTHONPATH=things.py:. python3 -m pytest tests/test_things_adapter.py -v
```

Expected: all tests pass, including the local fixture compatibility test. In a clean clone without the ignored reference directory, that one test skips and fake-API tests still pass.

- [ ] **Step 7: Commit only adapter files**

```bash
git add -- src/things_adapter.py tests/test_things_adapter.py
git commit --only -m $'feat: read Things snapshots safely\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/things_adapter.py tests/test_things_adapter.py
```

---

### Task 3: Markdown Contract

**Files:**
- Create: `src/markdown.py`
- Create: `tests/test_markdown.py`

**Interfaces:**
- Consumes: `TaskSnapshot`, `ChecklistItem`.
- Produces: `GENERATED_MARKER: str`; `escape_inline(value: str) -> str`; `render_task(task: TaskSnapshot) -> str`; `render_document(title: str, tasks: Sequence[TaskSnapshot]) -> str`; `is_managed_markdown(content: str) -> bool`.

- [ ] **Step 1: Write exact Markdown contract tests**

Create `tests/test_markdown.py`:

```python
from src.markdown import GENERATED_MARKER, render_document, render_task
from src.models import ChecklistItem, TaskSnapshot


def test_render_task_includes_supported_metadata_and_omits_missing_fields():
    task = TaskSnapshot(
        uuid="TASK-1",
        title="Release [v1]",
        status="incomplete",
        project_title="Product",
        area_title="Work",
        heading_title="Next",
        notes="first line\n- nested-looking line",
        tags=("important tag", "work"),
        checklist=(
            ChecklistItem(uuid="ITEM-1", title="Review *copy*", status="completed"),
        ),
        created="2026-09-04 09:00",
        modified="2026-09-04 10:00",
        deadline="2026-09-10",
    )

    rendered = render_task(task)

    assert rendered.startswith("## [ ] Release \\[v1\\]\n<!-- uuid: TASK-1 -->")
    assert "- **项目**: Product" in rendered
    assert "- **截止日期**: 2026-09-10" in rendered
    assert "- **开始日期**" not in rendered
    assert "优先级" not in rendered
    assert "Evening" not in rendered
    assert "  first line\n  - nested-looking line" in rendered
    assert "  - [x] Review \\*copy\\* <!-- uuid: ITEM-1 -->" in rendered


def test_status_markers_are_stable():
    assert render_task(TaskSnapshot("1", "open", "incomplete")).startswith("## [ ]")
    assert render_task(TaskSnapshot("2", "done", "completed")).startswith("## [x]")
    assert render_task(TaskSnapshot("3", "no", "canceled")).startswith("## [-]")


def test_document_has_marker_title_and_stable_separator():
    task = TaskSnapshot("TASK-1", "one", "incomplete")

    rendered = render_document("Inbox", [task])

    assert rendered.startswith(f"{GENERATED_MARKER}\n# Inbox\n\n")
    assert rendered.endswith("\n---\n")


def test_empty_document_remains_managed_and_deterministic():
    assert render_document("Today", []) == f"{GENERATED_MARKER}\n# Today\n"
```

- [ ] **Step 2: Run Markdown tests and verify missing module**

```bash
python3 -m pytest tests/test_markdown.py -v
```

Expected: collection fails because `src.markdown` does not exist.

- [ ] **Step 3: Implement inline escaping and field rendering**

Create `src/markdown.py` with marker:

```python
GENERATED_MARKER = "<!-- generated-by: things3-github-sync; do not edit -->"
```

`escape_inline` must normalize CRLF/CR to LF, replace embedded newlines with spaces, backslash-escape `\\`, `` ` ``, `*`, `_`, `[`, `]`, `<`, `>`, and collapse repeated whitespace. It must not prepend `#` to tags; tags render as `#important-tag` after replacing tag-internal whitespace with `-` and escaping structural characters.

Use this field order exactly when values exist:

1. 创建时间
2. 修改时间
3. 开始日期
4. 截止日期
5. 提醒时间
6. 项目
7. 领域
8. 标题分组
9. 标签
10. 备注
11. 子任务

Notes are normalized to LF, trailing blank lines removed, and every line prefixed by two spaces. Empty notes are omitted. Checklist markers use the same status mapping as tasks and include `<!-- uuid: ... -->`; if an item has `stop_date`, append `— 完成时间: <escaped value>` before the UUID comment.

- [ ] **Step 4: Implement document rendering and managed detection**

`render_task` ends with one newline but no separator. `render_document` emits marker, H1 title, then task blocks separated by `\n---\n`; a nonempty document ends with `\n---\n`, while an empty document ends immediately after the title newline. `is_managed_markdown` checks only whether the first line equals `GENERATED_MARKER`.

- [ ] **Step 5: Run Markdown tests**

```bash
python3 -m pytest tests/test_markdown.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit only Markdown files**

```bash
git add -- src/markdown.py tests/test_markdown.py
git commit --only -m $'feat: render deterministic task markdown\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/markdown.py tests/test_markdown.py
```

---

### Task 4: Snapshot Routing and Deterministic Rendering

**Files:**
- Create: `src/renderer.py`
- Create: `tests/conftest.py`
- Create: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `ThingsSnapshot`, `ContainerSnapshot`, `TaskSnapshot`, `ContainerPath`, `RenderedSnapshot`, `sanitize_path_segment`, `render_document`.
- Produces: `render_snapshot(snapshot: ThingsSnapshot) -> RenderedSnapshot`; `allocate_container_paths(projects: Sequence[ContainerSnapshot], areas: Sequence[ContainerSnapshot]) -> Tuple[ContainerPath, ...]`.

- [ ] **Step 1: Add reusable snapshot factories**

Create `tests/conftest.py`:

```python
import pytest

from src.models import ContainerSnapshot, TaskSnapshot, ThingsSnapshot


@pytest.fixture
def sample_snapshot():
    project = ContainerSnapshot("P1", "project", "Release", area_uuid="A1")
    area = ContainerSnapshot("A1", "area", "Work")
    tasks = (
        TaskSnapshot("T1", "Project task", "incomplete", project_uuid="P1", area_uuid="A1", start="Anytime", index=2),
        TaskSnapshot("T2", "Area task", "incomplete", area_uuid="A1", start="Someday", index=1),
        TaskSnapshot("T3", "Inbox task", "incomplete", start="Inbox", index=0),
        TaskSnapshot("T4", "Done", "completed", project_uuid="P1", stop_date="2026-09-04 10:00"),
        TaskSnapshot("T5", "Canceled", "canceled", start="Anytime", stop_date="2026-09-03 10:00"),
    )
    return ThingsSnapshot(
        tasks=tasks,
        projects=(project,),
        areas=(area,),
        today_uuids=("T2", "T1"),
        upcoming_uuids=("T3",),
    )
```

- [ ] **Step 2: Write routing, empty-file, and collision tests**

Create `tests/test_renderer.py`:

```python
from pathlib import Path

from src.models import ContainerSnapshot, ThingsSnapshot
from src.renderer import allocate_container_paths, render_snapshot


def test_routes_each_task_to_one_primary_location_and_dynamic_views(sample_snapshot):
    rendered = render_snapshot(sample_snapshot)

    assert "Project task" in rendered.files[Path("Projects/Release/tasks.md")]
    assert "Project task" not in rendered.files[Path("Areas/Work/tasks.md")]
    assert "Area task" in rendered.files[Path("Areas/Work/tasks.md")]
    assert "Inbox task" in rendered.files[Path("Inbox.md")]
    assert "Done" in rendered.files[Path("Projects/Release/已完成.md")]
    assert "Canceled" in rendered.files[Path("已取消.md")]
    assert rendered.files[Path("Today.md")].index("Area task") < rendered.files[Path("Today.md")].index("Project task")
    assert "Inbox task" in rendered.files[Path("Upcoming.md")]


def test_emits_fixed_top_level_and_empty_container_files():
    snapshot = ThingsSnapshot(
        projects=(ContainerSnapshot("P1", "project", "Empty"),),
        areas=(ContainerSnapshot("A1", "area", "Quiet"),),
    )

    rendered = render_snapshot(snapshot)

    expected = {
        Path("Inbox.md"), Path("Today.md"), Path("Anytime.md"),
        Path("Someday.md"), Path("Upcoming.md"), Path("已完成.md"),
        Path("已取消.md"), Path("Projects/Empty/tasks.md"),
        Path("Projects/Empty/已完成.md"), Path("Projects/Empty/已取消.md"),
        Path("Areas/Quiet/tasks.md"), Path("Areas/Quiet/已完成.md"),
        Path("Areas/Quiet/已取消.md"),
    }
    assert expected <= set(rendered.files)


def test_case_insensitive_collisions_get_stable_uuid_suffixes():
    projects = (
        ContainerSnapshot("AAA11111", "project", "Release"),
        ContainerSnapshot("BBB22222", "project", "release"),
    )

    paths = allocate_container_paths(projects, ())

    assert {item.relative_dir for item in paths} == {
        Path("Projects/Release-AAA11111"),
        Path("Projects/release-BBB22222"),
    }


def test_render_is_independent_of_input_tuple_order(sample_snapshot):
    reversed_snapshot = ThingsSnapshot(
        tasks=tuple(reversed(sample_snapshot.tasks)),
        projects=sample_snapshot.projects,
        areas=sample_snapshot.areas,
        today_uuids=sample_snapshot.today_uuids,
        upcoming_uuids=sample_snapshot.upcoming_uuids,
    )
    assert render_snapshot(sample_snapshot).files == render_snapshot(reversed_snapshot).files
```

Also test invalid `start` values: incomplete top-level tasks whose `start` is absent or not Inbox/Anytime/Someday go to `Anytime.md` and emit a warning captured by `caplog`.

- [ ] **Step 3: Run renderer tests and verify missing module**

```bash
python3 -m pytest tests/test_renderer.py -v
```

Expected: collection fails because `src.renderer` does not exist.

- [ ] **Step 4: Implement case-insensitive path allocation**

Create `src/renderer.py`. For each kind, sanitize names first. Group by `sanitized.casefold()`. A singleton keeps the clean name; every member of a collision group gets `-<uuid[:8]>`. Sort entities by `(title.casefold(), uuid)` before allocation, and return `ContainerPath` sorted by `(kind, relative_dir.as_posix().casefold(), uuid)`.

Use fallbacks `project-<uuid[:8]>` and `area-<uuid[:8]>`. Project paths begin with `Projects`; Area paths begin with `Areas`.

- [ ] **Step 5: Implement routing and stable task ordering**

Build lookup maps by UUID. Route terminal statuses before start-list routing:

```python
def primary_file(task, project_paths, area_paths):
    if task.project_uuid in project_paths:
        base = project_paths[task.project_uuid]
    elif task.area_uuid in area_paths:
        base = area_paths[task.area_uuid]
    else:
        base = None

    if task.status == "completed":
        return (base / "已完成.md") if base else Path("已完成.md")
    if task.status == "canceled":
        return (base / "已取消.md") if base else Path("已取消.md")
    if base:
        return base / "tasks.md"
    return Path(f"{task.start if task.start in {'Inbox', 'Anytime', 'Someday'} else 'Anytime'}.md")
```

Stable primary-file sort key:

```python
(
    task.index,
    task.created or "",
    task.title.casefold(),
    task.uuid,
)
```

Terminal files sort newest `stop_date` first by creating a key that preserves deterministic descending order, or by sorting ascending on the same stable tuple with `reverse=True` and UUID as a final deterministic key. Dynamic views must follow `today_uuids` / `upcoming_uuids` order exactly, skipping UUIDs absent from the task map and logging each skip once.

Create all seven fixed top-level files and all three files for every active Project/Area, including empty ones. Titles must be human-readable path/context titles, not absolute paths. Return an immutable `RenderedSnapshot` whose mapping keys are relative `Path` values without `..` or absolute roots.

- [ ] **Step 6: Run renderer and upstream tests**

```bash
python3 -m pytest tests/test_markdown.py tests/test_renderer.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit only renderer files**

```bash
git add -- src/renderer.py tests/conftest.py tests/test_renderer.py
git commit --only -m $'feat: route Things snapshots into files\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/renderer.py tests/conftest.py tests/test_renderer.py
```

---

### Task 5: Atomic File Reconciliation and Manifest

**Files:**
- Create: `src/filesystem.py`
- Create: `tests/test_filesystem.py`

**Interfaces:**
- Consumes: `RenderedSnapshot`, `ContainerPath`, `ChangeSet`, `GENERATED_MARKER`, target repository `Path`.
- Produces: `MANIFEST_PATH = Path(".things3-sync-manifest.json")`; `Manifest`; `reconcile(repo_path: Path, rendered: RenderedSnapshot) -> ChangeSet`; `load_manifest(repo_path: Path) -> Manifest`.

- [ ] **Step 1: Write basic reconcile and ownership tests**

Create `tests/test_filesystem.py` with helpers that build `RenderedSnapshot`. Include:

```python
from pathlib import Path

from src.filesystem import MANIFEST_PATH, reconcile
from src.markdown import GENERATED_MARKER
from src.models import ContainerPath, RenderedSnapshot


def managed(title: str) -> str:
    return f"{GENERATED_MARKER}\n# {title}\n"


def test_reconcile_adds_files_and_manifest(tmp_path):
    rendered = RenderedSnapshot(
        files={Path("Inbox.md"): managed("Inbox")},
        containers=(),
    )

    changes = reconcile(tmp_path, rendered)

    assert changes.added == (Path(".things3-sync-manifest.json"), Path("Inbox.md"))
    assert (tmp_path / "Inbox.md").read_text() == managed("Inbox")
    assert (tmp_path / MANIFEST_PATH).exists()


def test_identical_reconcile_does_not_rewrite_or_report_changes(tmp_path):
    rendered = RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ())
    reconcile(tmp_path, rendered)
    before = (tmp_path / "Inbox.md").stat().st_mtime_ns

    changes = reconcile(tmp_path, rendered)

    assert not changes.changed
    assert (tmp_path / "Inbox.md").stat().st_mtime_ns == before


def test_removes_only_previous_managed_files(tmp_path):
    first = RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ())
    reconcile(tmp_path, first)
    stranger = tmp_path / "notes.md"
    stranger.write_text("keep me")

    changes = reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert Path("Inbox.md") in changes.deleted
    assert stranger.read_text() == "keep me"


def test_refuses_to_overwrite_unmarked_desired_path_before_any_write(tmp_path):
    (tmp_path / "Inbox.md").write_text("user-owned")
    rendered = RenderedSnapshot({
        Path("Anytime.md"): managed("Anytime"),
        Path("Inbox.md"): managed("Inbox"),
    }, ())

    with pytest.raises(ValueError, match="ownership conflict"):
        reconcile(tmp_path, rendered)

    assert (tmp_path / "Inbox.md").read_text() == "user-owned"
    assert not (tmp_path / "Anytime.md").exists()


def test_refuses_to_delete_previous_path_after_marker_is_removed(tmp_path, caplog):
    rendered = RenderedSnapshot({Path("Inbox.md"): managed("Inbox")}, ())
    reconcile(tmp_path, rendered)
    (tmp_path / "Inbox.md").write_text("user-owned now")

    changes = reconcile(tmp_path, RenderedSnapshot({}, ()))

    assert (tmp_path / "Inbox.md").read_text() == "user-owned now"
    assert Path("Inbox.md") not in changes.deleted
    assert "not deleting unmarked file" in caplog.text.lower()
```

Also add:

```python
def test_refuses_to_overwrite_unmarked_destination_before_any_write(tmp_path):
    (tmp_path / "Inbox.md").write_text("personal inbox")
    rendered = RenderedSnapshot(
        files={
            Path("Anytime.md"): managed("Anytime"),
            Path("Inbox.md"): managed("Inbox"),
        },
        containers=(),
    )

    with pytest.raises(FileExistsError, match="unmanaged destination"):
        reconcile(tmp_path, rendered)

    assert (tmp_path / "Inbox.md").read_text() == "personal inbox"
    assert not (tmp_path / "Anytime.md").exists()
```

- [ ] **Step 2: Write path escape and interrupted-write tests**

Add tests asserting that absolute paths and paths containing `..` raise `ValueError` before any disk mutation. Patch the private `_atomic_write` on the second output and assert no Git-facing `ChangeSet` is returned; the first successful file may exist, the old second file remains intact, and the next unpatched `reconcile` converges.

Patch `os.replace` for a single file to raise `OSError`; verify its original content remains and a `.tmp` file is not left behind.

- [ ] **Step 3: Run filesystem tests and verify missing module**

```bash
python3 -m pytest tests/test_filesystem.py -v
```

Expected: collection fails because `src.filesystem` does not exist.

- [ ] **Step 4: Implement manifest schema and safe loading**

Manifest JSON schema version 1:

```json
{
  "_generated_by": "things3-github-sync",
  "version": 1,
  "managed_files": ["Inbox.md"],
  "active_containers": {
    "project:P1": "Projects/Release"
  },
  "archived_containers": {}
}
```

Create frozen `Manifest` with tuple/mapping fields. `load_manifest` returns an empty version-1 manifest if absent. If JSON is malformed, marker is wrong, version is unsupported, paths are unsafe, or types are invalid, raise `ValueError` and perform no writes. Serialize with `ensure_ascii=False`, `indent=2`, `sort_keys=True`, and one trailing newline.

A relative path is safe only if it is nonempty, not absolute, contains no `..` component, and resolves under `repo_path` via `Path.resolve().is_relative_to(repo_path.resolve())`. Because Python 3.9 lacks `Path.is_relative_to`, implement a private helper using `candidate.relative_to(root)` inside `try/except ValueError`.

- [ ] **Step 5: Implement atomic writes and basic reconciliation**

`_atomic_write(path, content)` must:

1. Create parents with `mkdir(parents=True, exist_ok=True)`.
2. Use `tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False)`.
3. Write, flush, and `os.fsync` the descriptor.
4. Call `os.replace(temp_path, path)`.
5. In `finally`, unlink the temporary path if it still exists.

`reconcile` validates every desired path before touching disk, loads the previous manifest, and performs a complete preflight over all desired destinations. A destination may be written only when it is absent, already listed in the previous manifest, or its existing first line matches `GENERATED_MARKER`; an existing unmarked destination raises `FileExistsError` before any write. After preflight, compare exact UTF-8 text, write added/modified desired files in sorted path order, then handle stale files from the prior manifest. A stale Markdown file is deleted only when its first line matches `GENERATED_MARKER`; stale manifest-owned JSON is managed by schema rather than the Markdown marker. Remove empty directories only by walking known old container directories upward until `Projects`, `Areas`, or repository root, and only when `rmdir()` succeeds.

Write the new manifest last. If the manifest content itself is unchanged, do not rewrite it. Return sorted tuples in `ChangeSet`. Set `git_paths` to the sorted union of the previous manifest's managed paths, the new manifest's managed paths, the manifest path itself, and every added/modified/deleted path. This broader, still-explicit pathspec lets a later sync detect and commit managed working-tree changes left behind by an earlier Git failure even when no file needs rewriting on that later run.

- [ ] **Step 6: Run basic filesystem tests**

```bash
python3 -m pytest tests/test_filesystem.py -v
```

Expected: all basic ownership, safety, and atomicity tests pass.

- [ ] **Step 7: Commit only basic filesystem files**

```bash
git add -- src/filesystem.py tests/test_filesystem.py
git commit --only -m $'feat: reconcile managed files atomically\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/filesystem.py tests/test_filesystem.py
```

---

### Task 6: Container Rename and Persistent Archive Behavior

**Files:**
- Modify: `src/filesystem.py`
- Modify: `tests/test_filesystem.py`

**Interfaces:**
- Consumes/produces the same `reconcile()` and `Manifest` interfaces from Task 5; extends manifest state transitions without changing callers.

- [ ] **Step 1: Add failing rename and archive tests**

Add these scenarios to `tests/test_filesystem.py`:

1. Initial container `project:P1 -> Projects/Old`, followed by active `project:P1 -> Projects/New`: managed files appear under New and disappear under Old.
2. Old contains `personal.md`: it remains under Old, while managed files move to New; warning is logged.
3. Initial active `project:P1 -> Projects/Release`, followed by no active P1: managed files move to `Archived/Projects/Release-P1`, and manifest records the archived mapping.
4. Area A1 similarly moves to `Archived/Areas/Work-A1`.
5. Running the same absent-container snapshot again does not delete or duplicate archived files and returns no changes.
6. P1 reappears: active files are generated at the active path, while archived history remains.
7. P1 disappears again: the existing P1 archive is updated rather than creating `Release-P1-2`.

Use an eight-character sanitized UUID suffix. If UUID contains path-invalid characters, derive the suffix by replacing non-alphanumeric characters with `-` and truncating to eight; if no alphanumeric content remains, use the first eight hex characters of `sha256(uuid.encode()).hexdigest()`.

- [ ] **Step 2: Run archive tests and verify failures**

```bash
python3 -m pytest tests/test_filesystem.py -v
```

Expected: new archive tests fail because Task 5 only deletes stale active files.

- [ ] **Step 3: Implement manifest-based container transitions**

Before generic stale-file deletion, compare previous `active_containers` against `rendered.containers` by `<kind>:<uuid>`:

- Same key, changed active path: treat as rename. New desired files are already written; remove only marked stale managed files under old path. Leave unknown files and nonempty directories in place.
- Previous active key absent now: calculate a stable archive directory. Move each marked managed file using atomic read/write/delete semantics so the returned `ChangeSet` includes the old path as deleted and archive path as added or modified. Never call `shutil.move` on a directory containing unknown files.
- Previously archived key that remains absent: retain its archive files and mapping untouched; archived paths are excluded from stale deletion.
- Archived key that reappears: add it to active mappings but retain archived mapping and files as history.
- Re-archived key: reuse its manifest archive directory and overwrite only its managed archive files whose content changed.

Archive directory basename is `<sanitized-last-active-name>-<stable-uuid-suffix>`. The first archive path is persisted in the manifest so later title changes or reappearance do not create another archive directory.

Ensure all archive destinations pass the same repository containment validation. Manifest `managed_files` contains active managed files plus persistent archived managed files.

- [ ] **Step 4: Run filesystem tests and inspect deterministic manifest**

```bash
python3 -m pytest tests/test_filesystem.py -v
```

Expected: all tests pass; a second identical archive reconcile has an empty `ChangeSet`.

- [ ] **Step 5: Commit archive behavior**

```bash
git add -- src/filesystem.py tests/test_filesystem.py
git commit --only -m $'feat: preserve renamed and archived containers\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/filesystem.py tests/test_filesystem.py
```

---

### Task 7: Explicit-Path Git Operations

**Files:**
- Create: `src/git_ops.py`
- Create: `tests/test_git_ops.py`

**Interfaces:**
- Consumes: repository `Path`, `ChangeSet`, `AppConfig` Git fields.
- Produces: `PENDING_PUSH_REF = "refs/things3-sync/pending-push"`; `GitClient(repo_path: Path, timeout: float = 30.0, runner: Callable[..., CompletedProcess[str]] = subprocess.run)`; `GitClient.stage(paths: Sequence[Path], *, env: Optional[Mapping[str, str]] = None) -> bool`; `GitClient.commit(changes: ChangeSet, paths: Sequence[Path], now: Optional[datetime] = None) -> bool`; `GitClient.push(remote: str, branch: str) -> bool`; `GitClient.pending_push() -> bool`; `GitClient.sync(changes: ChangeSet, auto_commit: bool, auto_push: bool, remote: str, branch: str, now: Optional[datetime] = None) -> Tuple[bool, bool]`; `ChangeCounts(added: int, modified: int, deleted: int)`; `generate_commit_message(counts: ChangeCounts, now: datetime) -> str`.

- [ ] **Step 1: Write command, timeout, and control-flow tests**

Create `tests/test_git_ops.py` using an injected runner. Cover:

```python
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import Mock, call

import pytest

from src.git_ops import ChangeCounts, GitClient, generate_commit_message
from src.models import ChangeSet


def ok(command, **kwargs):
    return CompletedProcess(command, 0, stdout="", stderr="")


def test_stage_uses_only_explicit_paths(tmp_path):
    runner = Mock(side_effect=ok)
    client = GitClient(tmp_path, runner=runner)
    changes = ChangeSet(
        added=(Path("Inbox.md"),),
        deleted=(Path("Projects/Old/tasks.md"),),
    )

    assert client.stage(changes.git_paths or changes.paths)

    command = runner.call_args.args[0]
    assert command == [
        "git", "add", "--", "Inbox.md", "Projects/Old/tasks.md"
    ]
    assert "." not in command[3:]


def test_commit_message_has_exact_counts_and_time():
    counts = ChangeCounts(added=2, modified=1, deleted=1)
    message = generate_commit_message(counts, datetime(2026, 9, 4, 10, 30))
    assert message == "Update: 2026-09-04 10:30 | Added 2, Modified 1, Deleted 1"


def test_sync_stops_before_push_when_commit_fails(tmp_path):
    def runner(command, **kwargs):
        if command[:2] == ["git", "commit"]:
            return CompletedProcess(command, 1, "", "hook rejected")
        if command[:4] == ["git", "diff", "--cached", "--quiet"]:
            return CompletedProcess(command, 1, "", "")
        if command[:4] == ["git", "diff", "--cached", "--name-status"]:
            return CompletedProcess(command, 0, "A\0Inbox.md\0", "")
        return CompletedProcess(command, 0, "", "")

    runner = Mock(side_effect=runner)
    client = GitClient(tmp_path, runner=runner)

    committed, pushed = client.sync(
        ChangeSet(added=(Path("Inbox.md"),)),
        auto_commit=True,
        auto_push=True,
        remote="origin",
        branch="main",
    )

    assert (committed, pushed) == (False, False)
    assert all(call.args[0][1] != "push" for call in runner.call_args_list)


def test_timeout_is_logged_and_returns_false(tmp_path, caplog):
    runner = Mock(side_effect=TimeoutExpired(["git", "push"], 5))
    client = GitClient(tmp_path, timeout=5, runner=runner)
    assert not client.push("origin", "main")
    assert "timed out" in caplog.text.lower()
```

Also test an empty current `ChangeSet.paths` with nonempty `git_paths` still checks and commits a leftover managed diff; a truly empty `git_paths` makes no staging or commit call; `AUTO_COMMIT=false` stages nothing and returns `(False, False)`; push failure returns `(True, False)` after a successful commit and leaves `PENDING_PUSH_REF` pointing at that commit; a later no-diff sync retries push only when that ref exists; a successful push deletes the ref; unrelated local commits without that ref never trigger a retry push; stderr is included in error logs after credentials in `https://user:TOKEN@host/...` and `https://TOKEN@host/...` are replaced with `***@`; every runner invocation uses `cwd`, `capture_output=True`, `text=True`, `timeout`, and `check=False`.

- [ ] **Step 2: Run Git tests and verify missing module**

```bash
python3 -m pytest tests/test_git_ops.py -v
```

Expected: collection fails because `src.git_ops` does not exist.

- [ ] **Step 3: Implement one subprocess boundary**

Create `GitClient._run(args: Sequence[str]) -> Optional[CompletedProcess[str]]`. It prepends `git`, invokes the runner with the required options, catches `TimeoutExpired` and `OSError`, and returns `None` on infrastructure failure. Before logging command arguments or stderr, pass text through `_redact_credentials`: parse URL-shaped substrings with `urllib.parse`, replace nonempty URL userinfo with `***`, and additionally replace values matching case-insensitive `token=`, `auth-token=`, or `password=` query/key forms. Never log the environment overlay. Tests must assert the original credential substring is absent, not only that the replacement appears.

Implement stage using one sorted path list and `git add --`. Then detect staged changes only within those paths using:

```text
git diff --cached --quiet -- <paths>
```

Return code 0 means no staged diff, 1 means diff exists, and any other value is an error. This prevents an unrelated pre-staged file from causing the sync commit to proceed.

- [ ] **Step 4: Implement isolated commit without consuming unrelated staged files**

A normal `git commit -m` commits all staged changes, including user changes staged before the service runs. To preserve the specification, implement commit with a temporary index:

1. Create a temporary file path and remove the empty file so Git can initialize it.
2. Set `GIT_INDEX_FILE=<temporary path>` only for Git commands in the sync transaction.
3. Seed it with `git read-tree HEAD`.
4. Stage explicit managed paths into that index using `git add -- <paths>`.
5. Inspect the temporary index with `git diff --cached --quiet -- <paths>` and, when it differs, parse `git diff --cached --name-status -z -- <paths>` into `ChangeCounts`. Count `A` as added, `D` as deleted, and all other statuses including both paths of a rename/copy as one modified item.
6. Generate the commit message from these actual index counts, not only the current filesystem `ChangeSet`; this keeps recovery commits accurate when their writes happened in an earlier run.
7. Commit with `git commit -m <message>` using that index.
8. Remove the temporary index in `finally`.
9. After a successful commit advances `HEAD`, refresh only the managed paths in the caller's real index with `git reset -q HEAD -- <paths>`. This updates those entries to the new HEAD while leaving unrelated staged paths intact. If this refresh fails, log the inconsistency and return `committed=False` so the caller does not proceed to push.

Extend `_run` to accept an optional environment overlay that starts from `os.environ.copy()`. Never log the overlay. `GitClient.sync()` uses this isolated-index flow directly; `stage()` remains available for unit-level explicit path behavior but production `sync()` must not stage managed content in the caller's real index.

This is necessary because this repository already contains unrelated staged files, and the service must work safely in the same condition. The real-repository acceptance test must assert both that `user.txt` remains staged and that no managed path appears in `git diff --cached --name-only` after the isolated commit.

- [ ] **Step 5: Implement push and result semantics**

`sync()` behavior:

- `auto_commit is False`: return `(False, False)` without staging or push.
- `changes.git_paths` is empty: skip staging and commit checks. If `auto_push` is enabled, retry push only when `git show-ref --verify --quiet refs/things3-sync/pending-push` returns success.
- `changes.paths` may be empty while `changes.git_paths` is nonempty; still inspect and commit those managed paths to recover from a prior failed commit.
- After a successful isolated commit, set `refs/things3-sync/pending-push` to `HEAD` with `git update-ref` before reporting `committed=True`. If marking fails, return `(False, False)` and do not push because durable retry state was not established.
- `auto_push is False`: retain the pending ref and return `(committed, False)`. This records that a later run with push enabled may publish the sync commit.
- With `auto_push=True`, push after a new marked commit or when the pending ref already exists. Do not infer pending work from the branch's general ahead/behind state.
- Push command is exactly `git push <remote> <branch>` in the real repository environment.
- After push succeeds, delete the ref with `git update-ref -d refs/things3-sync/pending-push`; if ref deletion fails, log it and return `pushed=False` so the next run safely retries an idempotent push.
- Push success after a commit created in this invocation returns `(True, True)`; push failure after that commit returns `(True, False)`.
- A retry-only push with no new commit returns `(False, True)` on success and `(False, False)` on failure. These booleans always describe actions completed in the current invocation.

No Git operation raises for expected command errors; methods return false and log stderr. Invalid `auto_push=True, auto_commit=False` raises `ValueError` as a defensive invariant even though configuration already rejects it.

- [ ] **Step 6: Run Git tests**

```bash
python3 -m pytest tests/test_git_ops.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Add a real temporary-repository isolation test**

Add a test using system Git in `tmp_path`:

1. Initialize a repository and set local test identity.
2. Commit `base.txt`.
3. Modify and stage `user.txt` in the real index.
4. Create `Inbox.md` and call `GitClient.sync(ChangeSet(added=(Path("Inbox.md"),)), auto_commit=True, auto_push=False, ...)`.
5. Assert `git show --name-only --format= HEAD` contains only `Inbox.md`.
6. Assert `git diff --cached --name-only` still contains `user.txt`.

Run:

```bash
python3 -m pytest tests/test_git_ops.py -v
```

Expected: all mocked and real-local Git tests pass.

- [ ] **Step 8: Commit only Git files**

```bash
git add -- src/git_ops.py tests/test_git_ops.py
git commit --only -m $'feat: commit managed paths in isolation\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/git_ops.py tests/test_git_ops.py
```

---

### Task 8: Sync Engine Transaction Boundary

**Files:**
- Create: `src/sync_engine.py`
- Create: `tests/test_sync_engine.py`

**Interfaces:**
- Consumes: reader object with `read_snapshot() -> ThingsSnapshot`; renderer callable; reconciler callable; `GitClient.sync`; `AppConfig`.
- Produces: `SyncEngine(config: AppConfig, reader: SnapshotReader, git_client: GitClient, renderer=render_snapshot, reconciler=reconcile)`; `SyncEngine.sync() -> SyncResult`; `SyncEngine.sync_if_idle() -> bool`.

- [ ] **Step 1: Write orchestration and failure-boundary tests**

Create `tests/test_sync_engine.py` with mocks:

```python
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.models import ChangeSet, RenderedSnapshot, SyncResult, ThingsSnapshot
from src.sync_engine import SyncEngine


def config(repo_path):
    return Mock(
        repo_path=repo_path,
        auto_commit=True,
        auto_push=False,
        git_remote="origin",
        git_branch="main",
    )


def test_sync_runs_single_pipeline_in_order(tmp_path):
    snapshot = ThingsSnapshot()
    rendered = RenderedSnapshot({}, ())
    changes = ChangeSet(added=(Path("Inbox.md"),))
    calls = []
    reader = Mock(read_snapshot=Mock(side_effect=lambda: calls.append("read") or snapshot))
    renderer = Mock(side_effect=lambda value: calls.append("render") or rendered)
    reconciler = Mock(side_effect=lambda repo, value: calls.append("reconcile") or changes)
    git = Mock(sync=Mock(side_effect=lambda *args, **kwargs: calls.append("git") or (True, False)))
    engine = SyncEngine(config(tmp_path), reader, git, renderer, reconciler)

    result = engine.sync()

    assert calls == ["read", "render", "reconcile", "git"]
    assert result == SyncResult(changes, committed=True, pushed=False)


def test_read_failure_prevents_render_write_and_git(tmp_path):
    reader = Mock(read_snapshot=Mock(side_effect=OSError("locked")))
    renderer = Mock()
    reconciler = Mock()
    git = Mock()
    engine = SyncEngine(config(tmp_path), reader, git, renderer, reconciler)

    with pytest.raises(OSError, match="locked"):
        engine.sync()

    renderer.assert_not_called()
    reconciler.assert_not_called()
    git.sync.assert_not_called()


def test_no_file_changes_skips_git(tmp_path):
    engine = SyncEngine(
        config(tmp_path),
        Mock(read_snapshot=Mock(return_value=ThingsSnapshot())),
        Mock(),
        Mock(return_value=RenderedSnapshot({}, ())),
        Mock(return_value=ChangeSet()),
    )
    result = engine.sync()
    assert result == SyncResult(ChangeSet())
    engine.git_client.sync.assert_called_once_with(
        ChangeSet(),
        auto_commit=True,
        auto_push=False,
        remote="origin",
        branch="main",
    )
```

The empty-change test documents that the engine always hands the reconcile result to Git. `GitClient` decides that empty `git_paths` means no commands; when reconciliation reports no new writes but includes historical managed `git_paths`, it can recover a previous failed commit.

Add a two-thread test using events: the first `sync()` blocks inside the reader; a concurrent `sync_if_idle()` returns `False` immediately and does not call the reader a second time. After release, another `sync_if_idle()` succeeds.

- [ ] **Step 2: Run sync engine tests and verify missing module**

```bash
python3 -m pytest tests/test_sync_engine.py -v
```

Expected: collection fails because `src.sync_engine` does not exist.

- [ ] **Step 3: Implement pipeline and nonblocking lock API**

Create reader and Git protocols so tests do not depend on concrete classes. Store a `threading.Lock`. `sync()` acquires it blocking, logs monotonic duration in a `finally`, and allows read/render/reconcile exceptions to propagate after logging. Always hand the reconciler's `ChangeSet` to Git; `GitClient.sync()` performs no commands when `git_paths` is empty, but can recover historical managed changes when current `paths` is empty:

```python
committed, pushed = self.git_client.sync(
    changes,
    auto_commit=self.config.auto_commit,
    auto_push=self.config.auto_push,
    remote=self.config.git_remote,
    branch=self.config.git_branch,
)
return SyncResult(changes, committed, pushed)
```

`sync_if_idle()` attempts `lock.acquire(blocking=False)`. Avoid reacquiring the same lock by factoring the body into `_sync_locked()`. It returns `False` when busy and `True` after it performs a sync. The service layer will use the boolean to request one later rerun.

- [ ] **Step 4: Run sync engine and upstream tests**

```bash
python3 -m pytest tests/test_sync_engine.py tests/test_git_ops.py tests/test_filesystem.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit only sync engine files**

```bash
git add -- src/sync_engine.py tests/test_sync_engine.py
git commit --only -m $'feat: coordinate snapshot sync transactions\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/sync_engine.py tests/test_sync_engine.py
```

---

### Task 9: Database Watcher, Debounce, and Pending Rerun

**Files:**
- Create: `src/watcher.py`
- Create: `tests/test_watcher.py`

**Interfaces:**
- Consumes: database `Path`; callback `Callable[[], bool]` where false means engine busy.
- Produces: `DatabaseEventFilter(database_path: Path, request_sync: Callable[[], None])`; `DebouncedSync(request: Callable[[], bool], delay: float, timer_factory=threading.Timer)` with `notify()`, `start()`, `stop(wait: bool = True)`; `DatabaseWatcher(database_path: Path, debounce: DebouncedSync, observer_factory=Observer)` with `start()` and `stop()`.

- [ ] **Step 1: Write event filtering tests**

Create `tests/test_watcher.py` with lightweight fake watchdog events:

```python
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from src.watcher import DatabaseEventFilter


def event(path, dest=None, is_directory=False):
    return SimpleNamespace(src_path=str(path), dest_path=str(dest) if dest else "", is_directory=is_directory)


def test_filter_accepts_sqlite_wal_and_shm(tmp_path):
    database = tmp_path / "main.sqlite"
    notify = Mock()
    handler = DatabaseEventFilter(database, notify)

    for suffix in ("", "-wal", "-shm"):
        handler.on_modified(event(Path(f"{database}{suffix}")))

    assert notify.call_count == 3


def test_filter_ignores_unrelated_and_directory_events(tmp_path):
    notify = Mock()
    handler = DatabaseEventFilter(tmp_path / "main.sqlite", notify)
    handler.on_modified(event(tmp_path / "other.sqlite"))
    handler.on_modified(event(tmp_path, is_directory=True))
    assert notify.call_count == 0
```

Cover created, moved destination, deleted and modified event methods because WAL files may appear/disappear.

- [ ] **Step 2: Write deterministic debounce tests with a fake timer**

Implement a `FakeTimer` in the test that records `start`, `cancel`, and exposes `fire()`. Tests must prove:

- Three `notify()` calls before fire cancel prior timers and invoke request once.
- A notification while `request()` is executing sets a pending flag; after request returns, exactly one new timer is scheduled.
- If `request()` returns false because the engine is busy, exactly one retry timer is scheduled.
- `stop()` cancels the timer, rejects later notifications, and optionally joins an executing worker.
- Delay must be positive.

- [ ] **Step 3: Run watcher tests and verify missing module**

```bash
python3 -m pytest tests/test_watcher.py -v
```

Expected: collection fails because `src.watcher` does not exist.

- [ ] **Step 4: Implement event filter and thread-safe debounce state machine**

Subclass `watchdog.events.FileSystemEventHandler`. Compare resolved/normalized string paths for the database, `database.name + "-wal"`, and `database.name + "-shm"`. Never read database content in an event callback.

`DebouncedSync` uses one `threading.Condition` and state fields `_timer`, `_running`, `_pending`, `_stopped`. `notify()` marks pending and resets a timer when not running; if running, it only marks pending. Timer fire clears `_timer`, marks running, calls `request()` outside the condition, then marks not running. It schedules one new timer when pending was set or request returned false. Catch callback exceptions, log them, and permit later notifications.

Use daemon timers, but `stop(wait=True)` must wait on the condition until `_running` becomes false. Do not hold the condition while executing the sync callback.

- [ ] **Step 5: Implement watchdog observer wrapper**

`DatabaseWatcher.start()` verifies `database_path.parent` exists, schedules one non-recursive watch on that parent, and starts the observer. `stop()` calls `observer.stop()` then `observer.join(timeout=10)`; if still alive, log an error. Starting twice or stopping before start is idempotent.

- [ ] **Step 6: Run watcher tests**

```bash
python3 -m pytest tests/test_watcher.py -v
```

Expected: all tests pass without real sleeps.

- [ ] **Step 7: Commit only watcher files**

```bash
git add -- src/watcher.py tests/test_watcher.py
git commit --only -m $'feat: debounce Things database events\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/watcher.py tests/test_watcher.py
```

---

### Task 10: Service Lifecycle and Main Entry Point

**Files:**
- Create: `src/service.py`
- Create: `main.py`
- Create: `tests/test_service.py`

**Interfaces:**
- Consumes: `AppConfig`, `ThingsReader`, `GitClient`, `SyncEngine`, `DebouncedSync`, `DatabaseWatcher`, `discover_database_path`, `setup_logging`.
- Produces: `SyncService(engine, watcher, debouncer, full_sync_interval, stop_event=None)`; `SyncService.run() -> None`; `SyncService.stop() -> None`; `build_service(config: AppConfig) -> SyncService`; `main() -> int`.

- [ ] **Step 1: Write lifecycle tests with no wall-clock waits**

Create `tests/test_service.py`. Inject a fake stop event whose `wait(timeout)` records timeouts and returns a scripted sequence. Cover:

```python
def test_run_performs_startup_sync_then_starts_watcher():
    calls = []
    engine = Mock(sync=Mock(side_effect=lambda: calls.append("startup")))
    watcher = Mock(start=Mock(side_effect=lambda: calls.append("watch")))
    stop_event = ScriptedEvent([True])
    service = SyncService(engine, watcher, Mock(), 3600, stop_event)

    service.run()

    assert calls == ["startup", "watch"]
    watcher.stop.assert_called_once()


def test_interval_uses_same_engine_entrypoint():
    engine = Mock()
    stop_event = ScriptedEvent([False, True])
    service = SyncService(engine, Mock(), Mock(), 60, stop_event)

    service.run()

    assert engine.sync.call_count == 2  # startup + one interval
```

Also verify shutdown ordering: watcher stops first, debouncer stops with `wait=True`, and only then `run()` returns. If startup sync raises, watcher never starts and the exception propagates. If an interval sync raises, it is logged and the loop continues until stopped.

- [ ] **Step 2: Run service tests and verify missing module**

```bash
python3 -m pytest tests/test_service.py -v
```

Expected: collection fails because `src.service` does not exist.

- [ ] **Step 3: Implement service lifecycle**

`run()` does:

```python
self.engine.sync()
self.watcher.start()
try:
    while not self.stop_event.wait(self.full_sync_interval):
        try:
            self.engine.sync()
        except Exception:
            logger.exception("Scheduled full sync failed")
finally:
    self.watcher.stop()
    self.debouncer.stop(wait=True)
```

`stop()` only sets the stop event and is idempotent. The debouncer callback is `engine.sync_if_idle`, so events during periodic sync produce one delayed rerun.

- [ ] **Step 4: Write main wiring and signal tests**

Add tests patching constructors in `main`:

- `build_service` wires the discovered path into both `ThingsReader` and `DatabaseWatcher`.
- `main()` loads `.env` with `dotenv.load_dotenv()`, builds configuration, initializes logs under `<project>/logs`, registers handlers for `SIGINT` and `SIGTERM`, and calls `service.run()`.
- Calling either captured signal handler calls `service.stop()`.
- Configuration error returns exit code 2 and logs one concise error.
- Runtime startup failure returns exit code 1.
- Normal shutdown returns 0.

- [ ] **Step 5: Implement production wiring**

Create `main.py` with `if __name__ == "__main__": raise SystemExit(main())`. Resolve logs relative to the project file, not the target repository. `build_service` constructs exactly one reader, one Git client, one engine, one debounce object, one watcher, and one service.

Signal handlers perform only `service.stop()` and a lightweight log call; they do not run sync or Git inside the signal handler.

- [ ] **Step 6: Run lifecycle tests**

```bash
python3 -m pytest tests/test_service.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit lifecycle files**

```bash
git add -- src/service.py main.py tests/test_service.py
git commit --only -m $'feat: run sync as a graceful service\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- src/service.py main.py tests/test_service.py
```

---

### Task 11: Interactive Setup and launchd Preview Generator

**Files:**
- Create: `setup.py`
- Create: `generate_launchd.py`
- Create: `tests/test_cli_tools.py`

**Interfaces:**
- Consumes: documented environment keys and project paths.
- Produces: `setup.write_env(repo_path: Path, destination: Path, *, auto_push: bool) -> None`; `generate_launchd.render_plist(project_dir: Path, python_path: Path) -> str`; `generate_launchd.write_plist(output: Path, project_dir: Path, python_path: Path) -> Path`.

- [ ] **Step 1: Write setup output tests**

Create `tests/test_cli_tools.py` and load root scripts with `importlib.util.spec_from_file_location` so `setup.py` is not confused with packaging tools. Test:

```python
def test_write_env_escapes_values_and_uses_defaults(tmp_path):
    repo = tmp_path / "repo with space"
    repo.mkdir()
    destination = tmp_path / ".env"

    setup_module.write_env(repo, destination, auto_push=False)

    text = destination.read_text()
    assert 'REPO_PATH="' + str(repo.resolve()) + '"' in text
    assert "AUTO_COMMIT=true" in text
    assert "AUTO_PUSH=false" in text
    assert "FULL_SYNC_INTERVAL=3600" in text
```

Test refusal to overwrite an existing `.env` unless `overwrite=True`; validation rejects a nonexistent path and a non-Git path using an injected runner. The interactive `main()` can be tested with injected `input_fn` and `output_fn`, avoiding terminal interaction.

- [ ] **Step 2: Write launchd XML tests**

Test that `render_plist`:

- Produces parseable XML via `plistlib.loads`.
- Uses absolute `sys.executable` and `<project>/main.py` in `ProgramArguments`.
- Sets `WorkingDirectory` to the project.
- Sets `RunAtLoad` and `KeepAlive` true.
- Writes stdout/stderr paths under `<project>/logs`.
- Does not contain `/Users/username` or shell-expanded `~`.

Test `write_plist` writes only the explicit project-local output path and creates its parent; it does not access `~/Library/LaunchAgents`.

- [ ] **Step 3: Run CLI tests and verify missing scripts**

```bash
python3 -m pytest tests/test_cli_tools.py -v
```

Expected: tests fail because `setup.py` and `generate_launchd.py` do not exist.

- [ ] **Step 4: Implement safe `.env` generation**

Use `shlex.quote` only for terminal display, not dotenv file encoding. Add a small `dotenv_quote` that wraps values in double quotes and escapes backslash, double quote, newline, and carriage return. Write through a temporary sibling and `os.replace`.

Interactive behavior:

1. Prompt for an existing local Git repository.
2. Validate via `git rev-parse --is-inside-work-tree` with 30-second timeout.
3. Ask whether automatic push is enabled, default yes.
4. Write `.env` in the project root.
5. If `.env` exists, print its path and exit 1 rather than overwrite.
6. Print the exact next foreground-run command as informational output.

The setup script must not clone repositories, configure credentials, install packages, or load launchd.

- [ ] **Step 5: Implement plist rendering with `plistlib`**

Build a Python dictionary and use:

```python
plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False).decode("utf-8")
```

Use label `com.things3githubsync.agent`. Default output is `<project>/build/com.things3githubsync.agent.plist`. Ensure logs directory exists when writing preview. The CLI supports `--output` and `--python`, both resolved to absolute paths.

- [ ] **Step 6: Run CLI tests**

```bash
python3 -m pytest tests/test_cli_tools.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit only deployment tool files**

```bash
git add -- setup.py generate_launchd.py tests/test_cli_tools.py
git commit --only -m $'feat: add setup and launchd tooling\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- setup.py generate_launchd.py tests/test_cli_tools.py
```

---

### Task 12: End-to-End Local Integration

**Files:**
- Create: `tests/test_integration.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes all runtime interfaces; no new production API.
- Produces a test-only fixture adapter and acceptance coverage using a temporary Git repository.

- [ ] **Step 1: Add a deterministic in-memory API fixture**

Extend `tests/conftest.py` with a `MutableThingsAPI` whose dictionaries can be changed between reads. It implements only `todos`, `projects`, `areas`, `today`, and `upcoming`, honors status filtering, and records every call. Also provide a `git_repo` fixture that initializes a temporary repository, configures local identity, commits a seed `.keep`, and returns its path.

This fixture is preferred for mutations because editing the ignored SQLite fixture would couple tests to private schema. Keep the Task 2 real fixture test as the compatibility boundary with `things.py`.

- [ ] **Step 2: Write end-to-end snapshot-to-commit test**

Create `tests/test_integration.py`:

1. Build `AppConfig` directly with `auto_commit=True`, `auto_push=False`.
2. Point `ThingsReader` at an existing empty test file; fake API ignores filepath but asserts it is passed.
3. Run `SyncEngine.sync()` with real renderer, filesystem reconciler, and real local `GitClient`.
4. Assert expected top-level, Project, Area, terminal and dynamic files exist.
5. Assert HEAD commit includes only generated files and manifest.
6. Run again unchanged and assert HEAD SHA remains unchanged.

- [ ] **Step 3: Write title-change and move acceptance test**

After initial sync:

1. Change only T1 title and run sync.
2. Assert `git show --format= --unified=0 HEAD` has one removed title line and one added title line, with no unrelated metadata changes.
3. Move T1 from Inbox to Project P1 and run sync.
4. Assert old Inbox block is absent, Project block exists, and commit contains both affected paths.

- [ ] **Step 4: Write archive and unrelated-index acceptance test**

After initial Project export:

1. Add `Projects/Release/personal.md` without marker.
2. Stage an unrelated `user-note.md` in the real Git index.
3. Remove P1 and its tasks from fake API, then sync.
4. Assert managed files are under stable `Archived/Projects/...`, `personal.md` remains active, and warning was emitted.
5. Assert HEAD commit excludes `user-note.md` and `personal.md`.
6. Assert `git diff --cached --name-only` still contains `user-note.md`.

- [ ] **Step 5: Run integration tests and fix only contract mismatches**

```bash
python3 -m pytest tests/test_integration.py -v
```

Expected: all end-to-end tests pass. If a failure reveals interface disagreement, adjust the smallest owning module and its unit test in the same task; do not add a second sync path or bypass ownership checks.

- [ ] **Step 6: Run the complete suite with coverage**

```bash
python3 -m pytest tests -v --cov=src --cov-report=term-missing
```

Expected: all tests pass. Coverage should show exercised branches in adapter retry, path routing, ownership deletion, Git failure, debounce, and service shutdown; no fixed numeric coverage gate is introduced for the MVP.

- [ ] **Step 7: Commit integration tests and any contract corrections**

Stage only files actually changed by this task, then use `--only`. Typical command:

```bash
git add -- tests/conftest.py tests/test_integration.py
git commit --only -m $'test: verify local sync end to end\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- tests/conftest.py tests/test_integration.py
```

If production files required corrections, append their explicit paths to both commands and describe those corrections in the commit body.

---

### Task 13: User Documentation and Source-of-Truth Alignment

**Files:**
- Create: `README.md`
- Modify: `Agent.md`

**Interfaces:**
- Consumes finalized behavior and commands from Tasks 1–12.
- Produces complete operator documentation and an accurate project checklist.

- [ ] **Step 1: Write README as an executable operator guide**

Create `README.md` with these sections and exact verified command categories:

1. What the service does and its one-way/read-only boundary.
2. Requirements: macOS, Things3, Python 3.9+, Git, existing authenticated remote.
3. Installation with virtual environment and `requirements.txt` / `requirements-dev.txt`.
4. Configuration table for every `.env.example` key, including defaults and constraints.
5. Interactive setup command.
6. Foreground run command.
7. Output tree and one complete Markdown example.
8. File ownership marker and stranger-file preservation.
9. Git behavior, temporary-index isolation, auto commit/push switches, and push-failure recovery.
10. launchd preview generation, explicit copy/load/unload steps, and log locations.
11. Test commands, including the optional local reference fixture path.
12. Troubleshooting for database not found, privacy permissions, Git authentication, remote ahead, malformed manifest, and shutdown timeout.
13. Known limitations matching the specification's non-goals.

Do not claim real GitHub push, seven-day soak, or 1000-task performance results unless those checks have actually run and their evidence is recorded.

- [ ] **Step 2: Align Agent.md with the implemented API and MVP**

Modify `Agent.md` so it no longer claims public `Task`, `Project`, or `Area` objects. Document that `things.py` returns dictionaries and `src/things_adapter.py` creates immutable internal models. Update:

- Modern `ThingsData-*` database path before the legacy fallback.
- Python 3.9+.
- `things.py>=1.0.1,<2`.
- Markdown example without Priority or Evening.
- Deterministic snapshot strategy instead of separate incremental and validator write paths.
- Area archive semantics.
- `AUTO_COMMIT`, `AUTO_PUSH`, `GIT_REMOTE`, `GIT_BRANCH`, and Git timeout keys.

Mark only tasks demonstrably completed by the test suite. Leave performance soak, real GitHub, and real launchd lifecycle items unchecked, with a concise reason.

- [ ] **Step 3: Verify documentation does not require generated artifacts**

Keep the user's pre-existing staged `.gitignore` and `docs/CHANGELOG.md` byte-for-byte unchanged during this task. README may recommend ignore rules, but implementation correctness must not depend on modifying those files. Before and after documentation work, record and compare their staged blob IDs:

```bash
git rev-parse :.gitignore :docs/CHANGELOG.md
```

Expected: both object IDs remain identical. Generated `.env`, logs, coverage output and plist previews must be removed after verification or remain untracked; never add them to the documentation commit.

- [ ] **Step 4: Verify every documented command and internal link**

Run the non-destructive commands exactly as documented:

```bash
python3 -m pytest tests -v
```

```bash
python3 generate_launchd.py --output build/com.things3githubsync.agent.plist
```

Parse the generated plist:

```bash
python3 -c "import plistlib; plistlib.load(open('build/com.things3githubsync.agent.plist','rb')); print('plist ok')"
```

Remove only the generated project-local preview after inspecting it if `build/` is documented as disposable and ignored; otherwise retain it outside the commit. Do not load launchd or push to a real remote during automated verification.

Search README and Agent.md for unsupported promises:

```bash
rg -n "Priority|Evening|双向|自动.*(merge|rebase)|7 天|1000" README.md Agent.md
```

Expected: any matches appear only in limitations, historical roadmap, or explicitly unverified criteria.

- [ ] **Step 5: Commit documentation while preserving prior staged files**

Commit only README and Agent.md:

```bash
git add -- README.md Agent.md
git commit --only -m $'docs: document Things3 sync MVP\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>' -- README.md Agent.md
```

Expected: only these two files are included; `.gitignore` and `docs/CHANGELOG.md` remain staged with the same blob IDs recorded in Step 3. Confirm with:

```bash
git status --short
git show --name-status --format= HEAD
```

---

### Task 14: Final Verification and Branch Readiness

**Files:**
- Modify only if verification reveals a concrete defect: the owning source/test/documentation file.

**Interfaces:**
- Consumes complete project.
- Produces verification evidence and a clean, reviewable feature branch while preserving the user's staged `.gitignore`, staged `docs/CHANGELOG.md`, and untracked `.DS_Store` state.

- [ ] **Step 1: Run syntax and complete automated tests**

```bash
python3 -m compileall -q src main.py setup.py generate_launchd.py
```

```bash
python3 -m pytest tests -v --cov=src --cov-report=term-missing
```

Expected: both commands exit 0.

- [ ] **Step 2: Verify dependency and forbidden-operation constraints**

```bash
rg -n "git add \.|from things import (complete|url)|things\.(complete|url)\(|update-project|things:///update" src main.py setup.py generate_launchd.py
```

Expected: no production-code matches. Test assertions or README explanations may match only when separately searched.

Verify every third-party import is declared:

```bash
python3 - <<'PY'
from pathlib import Path
allowed = {"things", "watchdog", "dotenv", "pytest"}
for path in [*Path("src").glob("*.py"), Path("main.py"), Path("setup.py"), Path("generate_launchd.py")]:
    print(path)
print("Review non-stdlib imports against requirements.txt and requirements-dev.txt:", sorted(allowed))
PY
```

Then manually compare the short list; expected runtime third-party imports are only `things`, `watchdog`, and `dotenv`.

- [ ] **Step 3: Verify repository containment and index isolation acceptance cases**

Run the focused tests:

```bash
python3 -m pytest tests/test_filesystem.py tests/test_git_ops.py tests/test_integration.py -v
```

Expected: all tests pass, including path escape rejection, stranger-file preservation, archive persistence, and unrelated staged-file isolation.

- [ ] **Step 4: Inspect branch diff and commit boundaries**

```bash
git log --oneline --decorate main..HEAD
```

```bash
git diff --stat main...HEAD
```

```bash
git status --short
```

Expected:

- Feature commits are small and ordered by task.
- `.gitignore` and `docs/CHANGELOG.md` remain staged with their original blob IDs and are absent from feature commits.
- The existing `.DS_Store` file remains untracked and untouched.
- No generated `.env`, logs, plist preview, SQLite database, WAL/SHM, coverage file, cache, or virtual environment appears in branch commits.

- [ ] **Step 5: Run a final specification coverage audit**

Compare the implementation against `docs/superpowers/specs/2026-09-04-things3-sync-mvp-design.md` and record in the final handoff:

- Startup, event, and interval triggers use `SyncEngine.sync` or `sync_if_idle` only.
- Read failure precedes every write.
- Render output is deterministic.
- File writes are content-aware and atomic.
- Archive history persists.
- Git commits isolate managed files from the real index.
- Auto commit and push switches work.
- SIGINT and SIGTERM stop the service gracefully.
- Setup and launchd tooling do not make implicit system changes.
- Manual-only checks are labeled as such.

If this audit reveals a defect, add a failing regression test, implement the smallest correction, rerun the focused and full suites, and commit only the correction paths with a conventional message and `--only`.

- [ ] **Step 6: Prepare the implementation handoff**

Report:

- Branch name and commit range.
- Test and compile results.
- Optional fixture compatibility result or skip reason.
- Manual checks not executed: real Things mutation observation, real GitHub push, launchd load/unload, seven-day soak, and 1000-task timing.
- Preserved pre-existing working-tree state.

Do not merge, push, load launchd, or delete the existing `.DS_Store` file without a separate explicit instruction.
