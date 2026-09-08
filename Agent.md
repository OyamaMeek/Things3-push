# Things3 to Git Markdown Sync MVP

## Scope

This macOS service reads Things3 data and writes a deterministic Markdown representation to a configured local Git work tree. The data flow is:

```text
Things3 SQLite database (read-only)
  -> things.py dictionary API
  -> immutable ThingsSnapshot models
  -> deterministic Markdown renderer
  -> atomic reconciliation and ownership manifest
  -> isolated Git commit / optional push
```

The MVP never writes to Things3. It does not pull, merge, rebase, resolve Git conflicts, or load a launchd service.

## Runtime And Dependencies

- macOS with Things3.
- Python 3.9+.
- Git work tree at `REPO_PATH`.
- `things.py>=1.0.1,<2`, `watchdog>=2.1,<7`, and `python-dotenv>=0.19,<2`.

`things.py` exposes read functions that return sparse dictionaries; it does not expose public `Task`, `Project`, or `Area` object classes for this project. `src/things_adapter.py` normalizes those dictionaries into frozen `TaskSnapshot`, `ContainerSnapshot`, `ChecklistItem`, and `ThingsSnapshot` models.

Database discovery honors explicit `THINGSDB` first. Otherwise it searches `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-*/Things Database.thingsdatabase/main.sqlite` before the legacy database location.

## Components

- `main.py`: loads `.env`, configures logging, installs signal handlers, and runs the service.
- `src/config.py`: validates environment configuration and local Git branch state.
- `src/things_adapter.py`: read-only database discovery, API access, normalization, and retry.
- `src/renderer.py` and `src/markdown.py`: deterministic snapshot-to-Markdown routing and rendering.
- `src/filesystem.py`: atomic reconciliation, ownership validation, persistent container archive handling, and manifest updates.
- `src/git_ops.py`: explicit-path Git operations through a temporary index and pending-push recovery.
- `src/sync_engine.py`: serialized snapshot transaction boundary.
- `src/watcher.py`: SQLite/WAL/SHM watcher and debounced sync scheduling.
- `src/service.py`: startup sync, periodic sync, lifecycle ownership, and graceful shutdown.
- `setup.py`: interactive `.env` creation only.
- `generate_launchd.py`: project-local plist preview generation only.

## Output Contract

The renderer produces root views (`Inbox.md`, `Today.md`, `Anytime.md`, `Someday.md`, `Upcoming.md`, `已完成.md`, `已取消.md`) and per-container `tasks.md`, `已完成.md`, and `已取消.md` files. Projects and areas are routed under `Projects/` and `Areas/`; safely removable historical containers move to `Archived/`.

Every generated document starts with:

```markdown
<!-- generated-by: things3-github-sync; do not edit -->
```

Example task block:

```markdown
## [ ] Prepare release notes
<!-- uuid: TASK-UUID -->
- **创建时间**: 2026-09-08 10:00
- **修改时间**: 2026-09-08 10:30
- **标签**: #work #release
- **备注**:
  Confirm the changelog entries.
- **子任务**:
  - [ ] Review draft <!-- uuid: ITEM-UUID -->
```

The manifest `.things3-sync-manifest.json` is the source of ownership for generated paths. Unknown files are preserved. The MVP uses one complete, deterministic snapshot rendering path for startup, watched, and scheduled syncs; it does not maintain separate incremental writer and validator paths.

## Configuration

`.env.example` is the configuration source of truth. Supported keys:

```text
REPO_PATH                 required existing Git work tree
THINGSDB                  optional explicit database path
LOG_LEVEL                 INFO by default
LOG_MAX_BYTES             10485760 by default, positive
LOG_BACKUP_COUNT          5 by default, non-negative
WATCH_DEBOUNCE_SECONDS    2 by default, positive
FULL_SYNC_INTERVAL        3600 by default, positive
AUTO_COMMIT               true by default
AUTO_PUSH                 true by default; requires AUTO_COMMIT=true
GIT_REMOTE                origin by default
GIT_BRANCH                main by default; must be checked out
GIT_TIMEOUT_SECONDS       30 by default, positive
```

## Operations

Create local configuration with `python setup.py`. It validates a supplied Git work tree and does not clone repositories, set credentials, install dependencies, or touch launchd.

Run the foreground service with `python main.py`. It completes an initial sync, starts the database watcher, and then performs interval syncs. `SIGINT` and `SIGTERM` request orderly shutdown.

Create a plist preview with:

```bash
python generate_launchd.py --output build/com.things3githubsync.agent.plist
```

The default preview path and `logs/` directory are project-local. Operators install, load, and unload a copy in `~/Library/LaunchAgents/` themselves. Application logs are `logs/sync.log`; plist stdout and stderr are `logs/launchd.out.log` and `logs/launchd.err.log`.

## Git Rules

Git commands have configured timeouts and use explicit managed pathspecs. Commits run through a temporary `GIT_INDEX_FILE` so unrelated staged changes are not included. A successful local commit that cannot be pushed is marked for retry on a later sync. No automatic remote reconciliation is attempted.

Do not use `git add .`. Do not add `.env`, credentials, generated logs, plist previews, temporary outputs, or unrelated working-tree changes to a commit.

## Delivery Checklist

- [x] Immutable models and environment configuration.
- [x] Read-only Things dictionary adapter with modern database discovery and retry.
- [x] Deterministic Markdown rendering, routing, and container path handling.
- [x] Atomic reconciliation, manifest validation, stranger-file preservation, and archives.
- [x] Explicit-path Git commits, push controls, credential redaction, and pending-push recovery.
- [x] Serialized sync engine, SQLite/WAL/SHM watcher, debouncing, service lifecycle, and signal handling.
- [x] Interactive setup and project-local launchd preview tooling.
- [x] Automated unit and temporary-repository integration coverage.
- [ ] Real Things3 observation: requires a user workstation and live database changes.
- [ ] Real remote push: requires an operator-configured authenticated remote.
- [ ] launchd load/unload lifecycle: requires explicit system installation by an operator.
- [ ] Extended soak and large-dataset timing: no recorded measurement evidence.
