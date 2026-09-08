# things3-github-sync

A macOS background service that keeps a **read-only, one-way** copy of your
[Things 3](https://culturedcode.com/things/) task database in a local Git
repository as deterministic Markdown.

The service never modifies Things. It reads the database through the
[`things.py`](https://github.com/ilkka/thing.py) read-only API, renders a
complete snapshot into Markdown files, and commits and (optionally) pushes
those files to a Git remote.

## Features

- **Read-only boundary** — only `todos`, `projects`, `areas`, `today`, and
  `upcoming` are read. No mutation APIs are used.
- **Deterministic output** — the same Things database always renders identical
  Markdown, independent of input ordering.
- **Full snapshot, not incremental** — every sync rewrites the entire managed
  file set, so the repository converges to a single source of truth.
- **Atomic reconciliation** — files are written through sibling temp files and
  `os.replace`; a crash mid-write leaves the previous state intact.
- **Safe Git isolation** — sync commits use a temporary index so unrelated
  staged changes in the user's real index are never consumed.
- **Container history** — renamed projects/areas are moved, and deleted
  containers are archived under `Archived/` rather than discarded.
- **Database watcher** — changes to the Things SQLite database (including WAL
  and SHM sidecar files) trigger a debounced re-sync.
- **Graceful shutdown** — SIGINT and SIGTERM stop the service after the current
  sync finishes.

## Requirements

- macOS with Things 3 installed.
- Python 3.9 or later.
- Git available on `PATH`.
- An existing Git repository with an authenticated remote configured.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # for tests
```

## Configuration

Run the interactive setup wizard to generate `.env`:

```bash
python3 setup.py
```

It prompts for your local Git repository path, validates it with
`git rev-parse --is-inside-work-tree`, asks whether automatic push is enabled,
and writes `.env` in the project root.

You can also create `.env` manually. Every key, default, and constraint:

| Key | Default | Notes |
| --- | --- | --- |
| `REPO_PATH` | *required* | Existing local Git work tree |
| `THINGSDB` | auto-discovered | Optional explicit path to `main.sqlite` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_MAX_BYTES` | `10485760` | Rotating log size in bytes |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated logs to keep |
| `WATCH_DEBOUNCE_SECONDS` | `2` | Database change quiet period |
| `FULL_SYNC_INTERVAL` | `3600` | Periodic full sync in seconds |
| `AUTO_COMMIT` | `true` | Commit managed changes |
| `AUTO_PUSH` | `true` | Push after commit; requires `AUTO_COMMIT=true` |
| `GIT_REMOTE` | `origin` | Remote to push to |
| `GIT_BRANCH` | `main` | Must match the checked-out branch |
| `GIT_TIMEOUT_SECONDS` | `30` | Timeout for Git commands |

## Running

```bash
python3 main.py
```

The service performs an initial sync, starts watching the Things database, and
runs a full sync every `FULL_SYNC_INTERVAL` seconds. Logs are written to
`logs/sync.log` in the project directory.

### launchd preview

To preview a launchd plist without loading it:

```bash
python3 generate_launchd.py --output build/com.things3githubsync.agent.plist
```

This writes a project-local preview only. To install it manually:

```bash
cp build/com.things3githubsync.agent.plist ~/Library/LaunchAgents/com.things3githubsync.agent.plist
launchctl load -w ~/Library/LaunchAgents/com.things3githubsync.agent.plist
```

To unload later:

```bash
launchctl unload -w ~/Library/LaunchAgents/com.things3githubsync.agent.plist
```

## Output tree

Managed files are written under the repository root:

```
Inbox.md
Today.md
Anytime.md
Someday.md
Upcoming.md
已完成.md
已取消.md
.things3-sync-manifest.json
Projects/<project-name>/tasks.md
Projects/<project-name>/已完成.md
Projects/<project-name>/已取消.md
Areas/<area-name>/tasks.md
Areas/<area-name>/已完成.md
Areas/<area-name>/已取消.md
Archived/Projects/<name>-<uuid>/
Archived/Areas/<name>-<uuid>/
```

Every generated file begins with a marker on its first line:

```
<!-- generated-by: things3-github-sync; do not edit -->
```

### Example Markdown

```markdown
<!-- generated-by: things3-github-sync; do not edit -->
# Inbox

## [ ] Ship release
<!-- uuid: TASK-1 -->

- **创建时间**: 2026-09-04 09:00
- **修改时间**: 2026-09-04 10:00
- **截止日期**: 2026-09-10
- **项目**: Release
- **领域**: Work
- **标题分组**: Next
- **标签**: #important-tag #work
- **备注**:
  first line
  second line
- **子任务**:
  - [x] Review \*copy\* — 完成时间: 2026-09-04 09:30 <!-- uuid: ITEM-1 -->
---
```

## File ownership and stranger files

- Only files beginning with the generated marker are managed and may be
  deleted or moved by the service.
- Files you place in the repository (for example `Projects/Release/personal.md`)
  are preserved and logged with a warning if they sit in a managed path.
- The manifest (`.things3-sync-manifest.json`) tracks every managed file and
  container, so a later sync can recover changes that a failed Git commit
  left behind.

## Git behavior

- Sync commits use a **temporary index**: managed paths are staged into a
  throwaway index, committed, then the real index is refreshed for only those
  paths. Unrelated staged files are never included.
- Commit messages follow the format
  `Update: YYYY-MM-DD HH:MM | Added N, Modified N, Deleted N`.
- A durable `refs/things3-sync/pending-push` reference marks a commit that
  still needs publishing. A later run with `AUTO_PUSH=true` retries the push
  only when that ref exists.
- The service never pulls, merges, rebases, or resolves remote conflicts.

## Testing

```bash
python3 -m pytest tests -v --cov=src --cov-report=term-missing
```

The optional fixture compatibility test reads the bundled `things.py` SQLite
fixture and is skipped when that directory is absent:

```bash
PYTHONPATH=things.py:. python3 -m pytest tests/test_things_adapter.py -v
```

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `Things database was not found` | Things 3 is closed, or `THINGSDB` points at the wrong path |
| `REPO_PATH must be a Git work tree` | The repository path is not a Git checkout |
| `GIT_BRANCH ... does not match checked-out branch` | The checked-out branch differs from `GIT_BRANCH` |
| `unmanaged destination` | A managed path is occupied by a file without the generated marker |
| `timed out` in logs | Git remote or network is slow; raise `GIT_TIMEOUT_SECONDS` |
| Sync stops without error | Detached HEAD is not supported; check out a named branch |
| Service will not shut down | A sync is in progress; it finishes before the watcher stops |

## Known limitations

- One-way sync from Things to Git; no import of Markdown back into Things.
- No pull, merge, rebase, or automatic conflict resolution.
- Priority, Evening, attachments, and repeating-rule fields are not exported.
- Runs on macOS only; the Things database path is macOS-specific.
- Real GitHub push, launchd load/unload, and long-running soak tests have not
  been executed in this environment and are documented as manual checks.

## License

See [LICENSE](LICENSE).