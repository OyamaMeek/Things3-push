# Things3 到 Git Markdown 同步

[![测试](https://github.com/OyamaMeek/Things3-push/actions/workflows/tests.yml/badge.svg)](https://github.com/OyamaMeek/Things3-push/actions/workflows/tests.yml)

[English](README.md)

需要从首次安装到日常维护的分步说明，请阅读[使用手册](docs/USAGE.zh-CN.md)。

将 macOS Things3 数据库中的任务以只读方式同步到已有 Git 仓库中的 Markdown 文件。服务只读取 Things3；不会写入 Things3、拉取远端、合并分支或修改系统 launchd 配置。

## 环境要求

- 已安装 Things3 且已获准访问其数据目录的 macOS。
- Python 3.9 或更高版本。
- Git 和已有的本地 Git 工作树。需要推送时，远端认证必须预先可用。

## 安装

```bash
git clone REPOSITORY_URL things3-github-sync
cd things3-github-sync
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

开发时安装测试依赖：

```bash
python -m pip install -r requirements-dev.txt
```

## 配置

复制 `.env.example` 为 `.env` 后编辑，或运行交互式配置：

```bash
python setup.py
```

该脚本会验证本地 Git 工作树并仅创建一次 `.env`。它不会克隆仓库、配置 Git 凭据、安装软件包或加载 launchd。

| 配置项 | 默认值 | 约束与用途 |
| --- | --- | --- |
| `REPO_PATH` | 无 | 必填，必须是已有本地 Git 工作树。 |
| `THINGSDB` | 无 | 可选 `main.sqlite` 路径，覆盖自动发现。 |
| `LOG_LEVEL` | `INFO` | `DEBUG`、`INFO`、`WARNING`、`ERROR` 或 `CRITICAL`。 |
| `LOG_MAX_BYTES` | `10485760` | `logs/sync.log` 轮转前的正整数最大字节数。 |
| `LOG_BACKUP_COUNT` | `5` | 轮转日志文件的非负保留数量。 |
| `WATCH_DEBOUNCE_SECONDS` | `2` | 文件变更同步前的正数静默窗口（秒）。 |
| `FULL_SYNC_INTERVAL` | `3600` | 定期完整快照同步的正数间隔（秒）。 |
| `AUTO_COMMIT` | `true` | 是否提交受同步器管理的路径。 |
| `AUTO_PUSH` | `true` | 是否推送；要求 `AUTO_COMMIT=true`。 |
| `GIT_REMOTE` | `origin` | 传给 `git push` 的远端名。 |
| `GIT_BRANCH` | `main` | 必须与当前检出的本地分支一致。 |
| `GIT_TIMEOUT_SECONDS` | `30` | 每条 Git 命令的正数超时（秒）。 |

未设置 `THINGSDB` 时，程序先搜索 `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/` 下的现代 `ThingsData-*` 目录，再回退至旧版 `Things Database.thingsdatabase/main.sqlite` 路径。

## 运行

以前台方式运行：

```bash
python main.py
```

程序启动时执行一次完整快照同步，监听 `main.sqlite`、`main.sqlite-wal` 和 `main.sqlite-shm`，并按间隔执行完整快照。`SIGINT` 与 `SIGTERM` 会请求优雅退出。日志写入 `logs/sync.log`，同时输出到标准错误。

## 输出

配置的仓库只会接收生成的 Markdown 文件与清单：

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
  Projects/<项目>/tasks.md
  Areas/<领域>/tasks.md
  Archived/<项目或领域>/
```

每个生成的 Markdown 文件都以所有权标识开头。任务区块是确定性的，且只包含读取 API 提供的字段：

```markdown
<!-- generated-by: things3-github-sync; do not edit -->
# Inbox

## [ ] 准备发布说明
<!-- uuid: TASK-UUID -->
- **创建时间**: 2026-09-08 10:00
- **修改时间**: 2026-09-08 10:30
- **开始日期**: 2026-09-09
- **截止日期**: 2026-09-12
- **标签**: #工作 #发布
- **备注**:
  确认更新日志条目。
- **子任务**:
  - [ ] 审阅草稿 <!-- uuid: ITEM-UUID -->
---
```

清单记录已生成文件以及活动或归档的容器路径。协调器只更新自己拥有的文件；没有精确标识的预存文件会被当作陌生文件保留，绝不会被覆盖或删除。安全时，被移除的容器会保留在 `Archived/` 下。

## Git 行为

仅发生变化且由清单管理的路径会被暂存。提交使用临时 Git index，以保留真实 index 中不相关的暂存项。`AUTO_COMMIT=true` 时，提交使用稳定的带时间戳更新消息；`AUTO_PUSH=true` 时，成功本地提交后推送 `GIT_BRANCH` 到 `GIT_REMOTE`。

推送失败会保留本地提交和待推送引用；后续无变化同步会重试该推送。程序不会执行 pull、merge、rebase 或自动解决冲突。请先在目标仓库中处理远端超前或认证失败，然后再次运行服务。

## launchd 预览

生成项目内 plist 预览：

```bash
python generate_launchd.py --output build/com.things3githubsync.agent.plist
```

生成器会写入预览并创建项目的 `logs/` 目录，但不会复制、加载、卸载或以其他方式修改系统 launchd 服务。检查预览后，如需部署，请显式执行：

```bash
cp build/com.things3githubsync.agent.plist ~/Library/LaunchAgents/com.things3githubsync.agent.plist
launchctl load ~/Library/LaunchAgents/com.things3githubsync.agent.plist
launchctl unload ~/Library/LaunchAgents/com.things3githubsync.agent.plist
```

plist 的标准输出和错误输出分别写入 `logs/launchd.out.log`、`logs/launchd.err.log`；应用日志仍在 `logs/sync.log`。

## 验证

运行自动化测试：

```bash
python -m pytest tests -v
```

可选的本地 `things.py/` 参考样本可加入导入路径：

```bash
PYTHONPATH=things.py:. python -m pytest tests -v
```

## 故障排查

| 现象 | 检查项 |
| --- | --- |
| 找不到数据库 | 设置本地 `main.sqlite` 的 `THINGSDB`，或确认现代/旧版 Things3 数据路径存在。 |
| 数据库读取失败 | 为终端或 launchd 进程授予读取 Things3 容器的 macOS 隐私权限，并在 Things3 完成当前写入后重试。 |
| Git 认证失败 | 在本项目外配置目标仓库凭据，再运行一次同步以重试待推送提交。 |
| 远端超前 | 手动获取并协调目标仓库；程序有意不执行 pull、merge 或 rebase。 |
| 清单格式错误 | 停止服务并检查 `.things3-sync-manifest.json`；恢复有效的受跟踪版本，或先确认同步器拥有的生成文件后再移除。 |
| 退出耗时较长 | 服务会等待进行中的同步和 watcher 清理；查看 `logs/sync.log` 中的失败阶段。 |

## 限制

- 这是从 Things3 到 Markdown 的单向导出；编辑生成的 Markdown 不会更新 Things3。
- 公共 `things.py` 读取 API 被视为稀疏字典数据，因此不会渲染其未公开的字段。
- 自动化测试使用样本和临时 Git 仓库；真实 Things3 访问、远端推送、launchd 加载与卸载仍需由操作者验收。
