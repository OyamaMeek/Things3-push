# Things3-GitHub-Sync

把 macOS 上的 **Things 3** 待办事项自动同步到本地 Git 仓库的 Markdown 文件，支持自动提交与推送。

## 功能概览

- **只读读取**：通过 `things.py` API 读取 Things 数据库，不修改 Things 任何数据。
- **结构化输出**：把任务、项目、领域、清单渲染为确定性的 Markdown 文档。
- **增量同步**：只对发生变化的文件执行写入，其余文件原样保留。
- **隔离提交**：使用临时 Git index 提交，避免影响仓库中其他手动修改。
- **防误删保护**：只有标记了生成器注释的托管文件才会被删除或移动。
- **实时监控**：监听 Things 数据库文件变化，防抖动后触发增量同步。
- **定时全量同步**：按配置间隔执行完整快照同步。
- **优雅退出**：响应 `SIGINT` / `SIGTERM`，清理后台 watcher 与防抖任务。

## 仓库结构

```
.
├── main.py              # 应用入口，加载配置并启动服务
├── setup.py             # 交互式生成 .env 配置
├── generate_launchd.py  # 生成 macOS launchd plist（后台常驻）
├── src/
│   ├── config.py        # 应用配置（AppConfig）
│   ├── service.py       # 服务编排（SyncService + build_service）
│   ├── sync_engine.py   # 单次同步事务（SyncEngine）
│   ├── things_adapter.py # Things 数据库只读适配器
│   ├── filesystem.py    # 原子化文件系统对账（reconcile）
│   ├── renderer.py      # 快照渲染为 Markdown 文件
│   ├── markdown.py      # Markdown 生成与解析
│   ├── watcher.py       # 数据库文件监控与防抖
│   ├── git_ops.py       # 隔离式 Git 提交/推送
│   ├── utils.py         # 日志、路径清洗、布尔解析
│   └── models.py        # 领域数据模型
├── tests/               # pytest 测试套件
└── docs/
    └── 使用文档.md      # 详细使用说明
```

## 安装

### 前置条件

- macOS 系统，已安装 Things 3。
- Python 3.9+。
- Git 已安装。

### 安装依赖

```bash
pip install -r requirements.txt
```

`requirements.txt` 包含：

```
things>=1.0.1,<2
watchdog>=2.1,<7
python-dotenv>=0.19,<2
```

### 安装 Things Python API

`things` 包需要访问 Things 数据库。安装方式见 [things.py](https://github.com/thingsapi/things.py)：

```bash
pip install things.py
```

## 配置

### 方式一：交互式生成配置

```bash
python setup.py
```

按提示输入本地 Git 仓库路径，并选择是否自动推送。配置会写入项目根目录的 `.env`：

```
REPO_PATH=/Users/you/my-things-repo
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

### 方式二：手动创建 `.env`

```bash
cp .env.example .env   # 如有模板
# 编辑 .env
```

### 配置项说明

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `REPO_PATH` | 必填 | 本地 Git 仓库目录，必须是已存在的 Git work tree |
| `THINGSDB` | 自动发现 | Things 数据库路径（`main.sqlite`），留空则自动查找 |
| `LOG_LEVEL` | `INFO` | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `LOG_MAX_BYTES` | `10485760` | 单个日志文件最大字节数（10 MB） |
| `LOG_BACKUP_COUNT` | `5` | 保留的轮转日志文件数 |
| `WATCH_DEBOUNCE_SECONDS` | `2` | 数据库变更后防抖延迟（秒） |
| `FULL_SYNC_INTERVAL` | `3600` | 定时全量同步间隔（秒，默认 1 小时） |
| `AUTO_COMMIT` | `true` | 是否自动提交 |
| `AUTO_PUSH` | `true` | 是否自动推送（需要 `AUTO_COMMIT=true`） |
| `GIT_REMOTE` | `origin` | 推送的远程名称 |
| `GIT_BRANCH` | `main` | 推送的分支，必须与当前检出分支一致 |
| `GIT_TIMEOUT_SECONDS` | `30` | Git 命令超时时间（秒） |

## 运行

### 前台运行

```bash
python main.py
```

日志会同时输出到终端和 `logs/sync.log`。按 `Ctrl+C` 或发送 `SIGTERM` 可优雅停止。

### 后台常驻（macOS launchd）

生成 launchd 配置 plist：

```bash
python generate_launchd.py
# 输出路径示例: build/com.things3githubsync.agent.plist
```

把生成的 plist 安装到 `~/Library/LaunchAgents/` 并加载：

```bash
cp build/com.things3githubsync.agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.things3githubsync.agent.plist
```

launchd 配置会在系统启动时自动运行，并在进程退出时自动重启（`KeepAlive`）。

## 输出结构

同步后的仓库大致如下：

```
my-things-repo/
├── .things3-sync-manifest.json   # 托管清单（自动生成，请勿手动修改）
├── Inbox.md
├── Today.md
├── Anytime.md
├── Someday.md
├── Upcoming.md
├── 已完成.md
├── 已取消.md
├── Projects/
│   └── 项目名-xxxxxxxx/
│       ├── tasks.md
│       ├── 已完成.md
│       └── 已取消.md
└── Areas/
    └── 领域名-xxxxxxxx/
        ├── tasks.md
        ├── 已完成.md
        └── 已取消.md
```

每个 Markdown 文件顶部都有生成标记：

```
<!-- generated-by: things3-github-sync; do not edit -->
```

同步器只管理带此标记的文件。你可以在仓库中自由放置其他文件，不会被覆盖或误删。

## 开发

### 安装开发依赖

```bash
pip install -r requirements-dev.txt
```

### 运行测试

```bash
pytest
```

### 运行带覆盖率的测试

```bash
pytest --cov=src --cov-report=term-missing
```

## 安全说明

- 所有 Git 命令均使用显式路径（`git add -- <path>`），不会误提交仓库中其他手动修改。
- 提交使用**临时隔离 index**，提交后刷新真实 index，不影响用户已有的暂存内容。
- 日志与错误输出中的 URL 凭据、`token=` / `password=` 参数会被自动脱敏。
- Things 数据库仅以只读方式访问，不会修改 Things 数据。
- `.env` 中若包含凭据，请勿提交到版本控制。

## 许可证

MIT License，见 [LICENSE](LICENSE)。

## 贡献

见 [SECURITY.md](SECURITY.md) 了解漏洞报告流程。