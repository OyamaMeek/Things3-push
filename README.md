# Things3 to Git Markdown Sync

[简体中文](README.zh-CN.md)

将 macOS Things3 数据库中的任务只读地同步到已有 Git 仓库中的 Markdown 文件。服务只从 Things3 读取数据；它不会写入 Things3、拉取远端、合并分支或修改系统 launchd 配置。

## Requirements

- macOS with Things3 installed and allowed to access its data directory.
- Python 3.9 or later.
- Git and an existing local Git work tree. To enable pushes, its configured remote must already have usable authentication.

## Install

```bash
git clone REPOSITORY_URL things3-github-sync
cd things3-github-sync
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Install test-only dependencies when developing:

```bash
python -m pip install -r requirements-dev.txt
```

## Configure

Copy `.env.example` to `.env` and edit it, or use the interactive setup command:

```bash
python setup.py
```

The setup script validates the supplied local Git work tree and creates `.env` once. It does not clone repositories, configure Git credentials, install packages, or load launchd.

| Key | Default | Constraint / purpose |
| --- | --- | --- |
| `REPO_PATH` | none | Required existing local Git work tree. |
| `THINGSDB` | none | Optional path to `main.sqlite`; overrides database discovery. |
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_MAX_BYTES` | `10485760` | Positive maximum size of `logs/sync.log` before rotation. |
| `LOG_BACKUP_COUNT` | `5` | Non-negative count of rotated log files. |
| `WATCH_DEBOUNCE_SECONDS` | `2` | Positive quiet period before a filesystem-triggered sync. |
| `FULL_SYNC_INTERVAL` | `3600` | Positive interval in seconds between scheduled snapshot syncs. |
| `AUTO_COMMIT` | `true` | Boolean controlling managed-path commits. |
| `AUTO_PUSH` | `true` | Boolean controlling pushes; requires `AUTO_COMMIT=true`. |
| `GIT_REMOTE` | `origin` | Remote passed to `git push`. |
| `GIT_BRANCH` | `main` | Must match the currently checked-out local branch. |
| `GIT_TIMEOUT_SECONDS` | `30` | Positive timeout in seconds for each Git command. |

Without `THINGSDB`, the reader first searches the modern `ThingsData-*` location under `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/`, then falls back to the legacy `Things Database.thingsdatabase/main.sqlite` location.

## Run

Run the service in the foreground:

```bash
python main.py
```

It performs one snapshot sync on startup, watches `main.sqlite`, `main.sqlite-wal`, and `main.sqlite-shm`, and schedules periodic full snapshots. `SIGINT` and `SIGTERM` request a graceful shutdown. Service logs are written to `logs/sync.log` and also emitted to standard error.

## Output

The configured repository receives only generated Markdown and the manifest:

```text
REPO_PATH/
  .things3-sync-manifest.json
  Inbox.md
  Today.md
  Anytime.md
  Someday.md
  Upcoming.md
  已完成.md
  已取消.md
  Projects/<project>/tasks.md
  Areas/<area>/tasks.md
  Archived/<project-or-area>/
```

Each generated Markdown file starts with an ownership marker. A task block is deterministic and includes only fields supplied by the read API:

```markdown
<!-- generated-by: things3-github-sync; do not edit -->
# Inbox

## [ ] Prepare release notes
<!-- uuid: TASK-UUID -->
- **创建时间**: 2026-09-08 10:00
- **修改时间**: 2026-09-08 10:30
- **开始日期**: 2026-09-09
- **截止日期**: 2026-09-12
- **标签**: #work #release
- **备注**:
  Confirm the changelog entries.
- **子任务**:
  - [ ] Review draft <!-- uuid: ITEM-UUID -->
---
```

The manifest records generated paths and active or archived container paths. Reconciliation updates only files it owns; a pre-existing file without the exact marker is treated as a stranger and is preserved rather than overwritten or deleted. Renamed containers keep their history, while removed containers are retained under `Archived/` when safe to do so.

## Git Behavior

Only manifest-owned changed paths are staged. Commits use a temporary Git index, preserving unrelated entries in the real index. With `AUTO_COMMIT=true`, commits use a stable timestamped update message. With `AUTO_PUSH=true`, the service pushes `GIT_BRANCH` to `GIT_REMOTE` after a successful local commit.

Push failures retain the local commit and a pending-push ref. A later no-change sync retries that pending push. The service does not run pull, merge, rebase, or automatic conflict resolution; resolve a remote-ahead state or authentication failure in the target repository, then run the service again.

## launchd Preview

Generate a project-local plist preview:

```bash
python generate_launchd.py --output build/com.things3githubsync.agent.plist
```

The generator writes the preview and creates the project `logs/` directory. It never copies, loads, unloads, or otherwise changes a system launchd service. Inspect the preview, then explicitly install it using the Python interpreter from the virtual environment:

```bash
cp build/com.things3githubsync.agent.plist ~/Library/LaunchAgents/com.things3githubsync.agent.plist
launchctl load ~/Library/LaunchAgents/com.things3githubsync.agent.plist
launchctl unload ~/Library/LaunchAgents/com.things3githubsync.agent.plist
```

The plist writes launchd stdout and stderr to `logs/launchd.out.log` and `logs/launchd.err.log`; application logs remain in `logs/sync.log`.

## Verify

Run the automated suite:

```bash
python -m pytest tests -v
```

The optional local `things.py/` reference fixture can be added to the import path when testing against that fixture:

```bash
PYTHONPATH=things.py:. python -m pytest tests -v
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Database not found | Set `THINGSDB` to the local `main.sqlite` path, or confirm the modern/legacy Things3 data path exists. |
| Database read fails | Grant the terminal or launchd process macOS privacy permission to read the Things3 container, then retry after Things3 finishes its current write. |
| Git authentication fails | Configure credentials for the target repository outside this project, then run another sync to retry the pending push. |
| Remote is ahead | Fetch and reconcile the target repository manually. The service intentionally performs no pull, merge, or rebase. |
| Malformed manifest | Stop the service and inspect `.things3-sync-manifest.json`; restore a valid tracked version or remove it only after confirming which generated files the service owns. |
| Shutdown takes time | The service waits for an in-progress sync and watcher cleanup. Check `logs/sync.log` for the failing stage. |

## Limitations

- This is a one-way Things3-to-Markdown export; editing generated Markdown does not update Things3.
- The public `things.py` read API is treated as sparse dictionary data, so fields it does not expose are not rendered.
- Automated tests use fixtures and temporary Git repositories. Real Things3 access, remote pushes, and launchd load/unload remain operator checks.
