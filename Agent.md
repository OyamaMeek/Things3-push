```markdown
# AGENTS.md - Things3 to GitHub Markdown Sync Agent

## Project Overview & Architecture

### Core Mission
自动监听 Things3 数据库变化，实时将任务数据转换为结构化 Markdown 文件，并通过 Git 同步到 GitHub 仓库，保持任务管理数据的版本化备份与可读性。

### Key Business Entities
- **Task（任务）**: Things3 核心实体，包含标题、状态、元数据、子任务
- **Project（项目）**: 任务容器，有独立文件夹结构
- **Area（领域）**: 更高层级的任务分组
- **Tag（标签）**: 跨项目的任务分类标记

### Core Data Flow
```
Things3 SQLite DB 
  ↓ (watchdog 监听文件变化)
things.py 库解析
  ↓ (数据模型转换)
Markdown Generator (增量更新策略)
  ↓ (文件系统写入)
Git Operations (auto commit & push)
  ↓
GitHub Repository (远程备份)
```

### Architecture Principles
- **事件驱动**: 文件监听 + 信号处理
- **增量优先**: 精确定位修改，减少 Git diff 噪音
- **容错设计**: 重试机制 + 日志追踪 + 全量校验兜底
- **零人工干预**: 后台服务 + 自动初始化

---

## Tech Stack & Dependencies

### Runtime Environment
- **OS**: macOS 10.14+（Things3 限定）
- **Python**: 3.6+ (推荐 3.9+)
- **Git**: 2.20+（系统命令行）

### Core Dependencies
```
things.py>=0.2.0        # Things3 数据库接口
watchdog>=2.1.0         # 文件系统监听
python-dotenv>=0.19.0   # 环境配置管理
```

### System Integration
- **launchd**: macOS 后台服务守护进程
- **Things3 数据库路径**: `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/Things Database.thingsdatabase/main.sqlite`

---

## Directory Structure & Conventions

### Project Structure
```
things3-github-sync/
├── .env                      # 配置文件（Git ignore）
├── .env.example              # 配置模板
├── requirements.txt          # Python 依赖
├── README.md                 # 用户文档
├── setup.py                  # 交互式初始化脚本
├── generate_launchd.py       # launchd plist 生成器
├── main.py                   # 主程序入口
├── src/
│   ├── __init__.py
│   ├── watcher.py            # 文件监听模块
│   ├── parser.py             # Things3 数据解析（基于 things.py）
│   ├── markdown_generator.py # Markdown 生成与增量更新
│   ├── git_ops.py            # Git 命令封装
│   ├── sync_engine.py        # 核心同步逻辑协调器
│   ├── validator.py          # 全量对比校验模块
│   └── utils.py              # 工具函数（文件名清理、日志等）
├── logs/                     # 日志目录（自动创建）
└── tests/                    # 单元测试（可选）
```

### Target Repository Structure（GitHub 仓库本地路径）
```
<REPO_PATH>/
├── Inbox.md
├── Today.md
├── Anytime.md
├── Someday.md
├── Upcoming.md
├── 已完成.md
├── 已取消.md
├── Projects/
│   ├── 项目A/
│   │   ├── tasks.md
│   │   ├── 已完成.md
│   │   └── 已取消.md
│   └── 项目B/
│       └── tasks.md
├── Areas/
│   ├── 工作/
│   │   ├── tasks.md
│   │   ├── 已完成.md
│   │   └── 已取消.md
│   └── 个人/
│       └── tasks.md
└── Archived/                 # 已归档的 Project/Area
    └── 旧项目/
```

### Markdown Format Standard
```markdown
## [ ] 任务标题
<!-- uuid: ABC123DEF456 -->
- **创建时间**: 2025-01-15 10:30
- **修改时间**: 2025-01-15 14:20
- **开始日期**: 2025-01-16
- **截止日期**: 2025-01-20
- **标签**: #工作 #重要
- **优先级**: High
- **特殊字段**: Evening
- **备注**: 
  任务的详细描述内容，支持多行
- **子任务**:
  - [ ] 子任务1 <!-- uuid: SUB123 -->
  - [x] 子任务2 <!-- uuid: SUB456 -->

---
```

### Naming Conventions
- **文件名清理**: 非法字符 (`/`, `:`, `?`, `*`, `<`, `>`, `|`, `"`) 替换为 `-`
- **UUID 注释**: 每个任务/子任务包含隐藏的 `<!-- uuid: xxx -->` 用于增量定位
- **状态标记**: `[ ]` 未完成, `[x]` 已完成, `[-]` 已取消

---

## Codex Operational Rules

### Pre-execution Checklist
在修改任何核心逻辑前，必须先读取并理解：
1. `.env` 配置文件格式（通过 `.env.example` 了解）
2. `things.py` 库的 API 文档（Task, Project, Area 对象结构）
3. 现有 Markdown 文件的格式约定（UUID 注释位置）
4. Git 仓库的当前状态（避免破坏现有提交）

### Coding Constraints

#### 严格禁止
- ❌ 直接修改 Things3 数据库（只读访问）
- ❌ 在 Markdown 中硬编码文件路径或用户信息
- ❌ 使用 `git add .`（必须明确指定文件）
- ❌ 引入未在 `requirements.txt` 声明的第三方库
- ❌ 阻塞式等待（所有 I/O 操作需配置超时）

#### 必须遵守
- ✅ 所有文件操作使用 `pathlib.Path`
- ✅ Git 命令通过 `subprocess.run()` 执行，捕获 stderr
- ✅ 数据库读取失败时，等待 10 秒重试，最多 3 次
- ✅ 每个函数配置日志记录（使用 `logging` 模块）
- ✅ 信号处理：捕获 `SIGINT`, `SIGTERM` 优雅退出

#### Error Handling Standard
```python
import logging
import subprocess
from pathlib import Path

def safe_git_operation(repo_path: Path, command: list) -> bool:
    """
    执行 Git 命令，记录错误但不中断主流程
  
    Returns:
        bool: 操作是否成功
    """
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        logging.info(f"Git command success: {' '.join(command)}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command failed: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logging.error(f"Git command timeout: {' '.join(command)}")
        return False
```

### Testing & Verification

#### Unit Test Requirements
- `tests/test_markdown_generator.py`: 测试 UUID 注释插入、任务章节定位
- `tests/test_parser.py`: 验证 Things3 数据解析的边界情况（空任务、特殊字符）
- `tests/test_git_ops.py`: Mock Git 命令，测试提交信息生成逻辑

#### Integration Test Scenarios
1. 创建任务 → 验证 Markdown 生成 → 检查 Git commit
2. 修改任务标题 → 验证仅该行被修改（Git diff 精确）
3. 移动任务（Inbox → Project）→ 验证旧文件删除 + 新文件创建
4. 删除 Project → 验证文件夹移动到 `Archived/`

---

## Verification Commands

### Environment Setup
```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 交互式初始化（生成 .env 和 launchd plist）
python setup.py
```

### Development Workflow
```bash
# 运行主程序（前台测试）
python main.py

# 检查日志
tail -f logs/sync_$(date +%Y-%m-%d).log

# 手动触发全量校验（调试用）
python -c "from src.validator import full_sync; full_sync()"
```

### Production Deployment
```bash
# 生成 launchd plist
python generate_launchd.py

# 加载服务
launchctl load ~/Library/LaunchAgents/com.things3sync.plist

# 查看服务状态
launchctl list | grep things3sync

# 卸载服务
launchctl unload ~/Library/LaunchAgents/com.things3sync.plist
```

### Code Quality Checks
```bash
# 代码格式化（推荐 black）
black src/ --line-length 100

# 类型检查（可选）
mypy src/ --ignore-missing-imports

# 运行测试
pytest tests/ -v --cov=src
```

---

## Configuration Specification

### .env File Format
```bash
# GitHub 仓库本地路径（已 clone 并配置认证）
REPO_PATH=/Users/username/Documents/things-backup

# 日志配置
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5

# 监听配置
WATCH_DEBOUNCE_SECONDS=2  # 防抖延迟（可选，默认立即提交）

# 全量校验间隔（秒）
FULL_SYNC_INTERVAL=3600  # 每小时一次
```

### .env.example Template
```bash
REPO_PATH=/path/to/your/github/repo
LOG_LEVEL=INFO
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
FULL_SYNC_INTERVAL=3600
```

---

## Phased Roadmap & Task Checklist

### Phase 1: Core Infrastructure（核心基础设施）
- [ ] **Task 1.1**: 创建项目目录结构，初始化 Git 仓库
- [ ] **Task 1.2**: 编写 `requirements.txt`，包含 `things.py`, `watchdog`, `python-dotenv`
- [ ] **Task 1.3**: 实现 `src/utils.py` 
  - 文件名清理函数 `sanitize_filename(name: str) -> str`
  - 日志初始化函数 `setup_logging(log_dir: Path, level: str)`
  - UUID 生成与注释解析函数
- [ ] **Task 1.4**: 编写 `.env.example` 模板

### Phase 2: Things3 Data Access（数据访问层）
- [ ] **Task 2.1**: 实现 `src/parser.py`
  - 封装 `things.py` 接口，提供统一数据模型
  - 函数：`get_all_tasks()`, `get_task_by_uuid()`, `get_projects()`, `get_areas()`
  - 处理已完成/已取消任务的过滤逻辑
- [ ] **Task 2.2**: 添加数据库读取重试机制（10 秒 × 3 次）
- [ ] **Task 2.3**: 编写 `tests/test_parser.py` 测试边界情况

### Phase 3: Markdown Generation Engine（Markdown 生成引擎）
- [ ] **Task 3.1**: 实现 `src/markdown_generator.py` 基础版
  - 函数：`generate_task_markdown(task) -> str`
  - 包含 UUID 注释、所有元数据字段、子任务嵌套列表
- [ ] **Task 3.2**: 实现增量更新逻辑
  - 函数：`update_task_in_file(file_path: Path, task_uuid: str, new_content: str)`
  - 通过正则表达式定位 `<!-- uuid: xxx -->` 章节
  - 精确替换该章节内容，保留文件其他部分
- [ ] **Task 3.3**: 实现文件结构管理
  - 函数：`get_task_file_path(task) -> Path` 根据任务类型返回正确路径
  - 处理 Inbox/Today/Anytime/Someday/Projects/Areas 的路径映射
- [ ] **Task 3.4**: 实现任务删除逻辑
  - 函数：`remove_task_from_file(file_path: Path, task_uuid: str)`
- [ ] **Task 3.5**: 编写 `tests/test_markdown_generator.py`

### Phase 4: Git Operations（Git 操作层）
- [ ] **Task 4.1**: 实现 `src/git_ops.py`
  - 函数：`git_add(repo_path: Path, files: list)`
  - 函数：`git_commit(repo_path: Path, message: str) -> bool`
  - 函数：`git_push(repo_path: Path) -> bool`
  - 所有操作包含错误处理和日志记录
- [ ] **Task 4.2**: 实现智能 commit message 生成
  - 函数：`generate_commit_message(changes: dict) -> str`
  - 格式：`Update: 2025-01-15 10:30 | Added 3, Modified 2, Deleted 1`
- [ ] **Task 4.3**: 编写 `tests/test_git_ops.py`（使用 Mock）

### Phase 5: Sync Engine（同步引擎）
- [ ] **Task 5.1**: 实现 `src/sync_engine.py` 核心协调器
  - 函数：`sync_changes(changed_tasks: list)`
  - 逻辑：解析任务 → 生成/更新 Markdown → Git 提交
- [ ] **Task 5.2**: 实现任务移动检测
  - 通过比对任务当前路径与 Markdown 文件位置
  - 删除旧位置章节 + 新位置创建
- [ ] **Task 5.3**: 实现 Project/Area 归档逻辑
  - 检测已删除的容器 → 移动文件夹到 `Archived/`
- [ ] **Task 5.4**: 实现动态视图（Today/Upcoming）更新
  - 每次全量重新生成 `Today.md`（只包含当天任务）
  - `Upcoming.md` 基于日期范围过滤

### Phase 6: File Watcher（文件监听）
- [ ] **Task 6.1**: 实现 `src/watcher.py`
  - 使用 `watchdog` 监听 Things3 SQLite 文件
  - 触发 `sync_engine.sync_changes()`
- [ ] **Task 6.2**: 添加监听中断检测
  - 如果全量校验正在进行 → 中断并重新开始
- [ ] **Task 6.3**: 实现优雅退出
  - 捕获 `SIGINT`, `SIGTERM` → 完成当前 Git 操作 → 退出

### Phase 7: Full Sync Validator（全量校验）
- [ ] **Task 7.1**: 实现 `src/validator.py`
  - 函数：`full_sync_validation(repo_path: Path)`
  - 遍历 Things3 所有任务 → 比对本地 Markdown
  - 缺失任务 → 生成；多余章节 → 删除；不一致 → 覆盖
- [ ] **Task 7.2**: 集成定时触发（每小时一次）
  - 使用 `threading.Timer` 或 `schedule` 库
- [ ] **Task 7.3**: 校验完成后生成特殊 commit
  - Message: `Full sync verification: 2025-01-15 14:00`

### Phase 8: Interactive Setup（交互式初始化）
- [ ] **Task 8.1**: 编写 `setup.py` 交互式配置脚本
  - 询问：GitHub 仓库本地路径
  - 验证路径存在且为 Git 仓库
  - 生成 `.env` 文件
- [ ] **Task 8.2**: 编写 `generate_launchd.py`
  - 读取 `.env` 中的路径
  - 生成 `~/Library/LaunchAgents/com.things3sync.plist`
  - 自动替换脚本路径、Python 解释器路径
- [ ] **Task 8.3**: 提供 launchd plist 模板
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
      <key>Label</key>
      <string>com.things3sync</string>
      <key>ProgramArguments</key>
      <array>
          <string>/path/to/venv/bin/python</string>
          <string>/path/to/main.py</string>
      </array>
      <key>RunAtLoad</key>
      <true/>
      <key>KeepAlive</key>
      <true/>
      <key>StandardOutPath</key>
      <string>/path/to/logs/launchd.out.log</string>
      <key>StandardErrorPath</key>
      <string>/path/to/logs/launchd.err.log</string>
  </dict>
  </plist>
  ```

### Phase 9: Main Entry Point（主入口）
- [ ] **Task 9.1**: 编写 `main.py`
  - 加载 `.env` 配置
  - 初始化日志系统
  - 启动文件监听
  - 启动全量校验定时器
  - 注册信号处理器
- [ ] **Task 9.2**: 添加启动时首次全量同步
  - 确保程序启动时数据一致

### Phase 10: Documentation & Testing（文档与测试）
- [ ] **Task 10.1**: 编写 `README.md` 用户文档
  - 安装步骤
  - 配置说明
  - 故障排查指南
- [ ] **Task 10.2**: 运行完整集成测试
  - 创建测试 Things3 任务 → 验证同步
  - 修改任务 → 验证 Git diff 精确性
  - 删除任务 → 验证 Markdown 清理
- [ ] **Task 10.3**: 性能测试
  - 1000+ 任务场景下的同步延迟
  - 全量校验耗时测试

### Phase 11: Edge Cases & Polish（边界情况与优化）
- [ ] **Task 11.1**: 处理极端情况
  - 任务标题超长（截断或换行）
  - 任务标题包含 Markdown 特殊字符（转义）
  - 空 Project/Area（保留文件夹结构）
- [ ] **Task 11.2**: Git 冲突处理
  - 如果远程有更新 → 先 pull 再 push（可选）
- [ ] **Task 11.3**: 添加性能监控
  - 每次同步耗时记录到日志
  - 数据库查询次数统计

---

## Codex Execution Guidelines

### Workflow for Each Task
1. **Read Context**: 查看相关现有代码和配置
2. **Implement**: 编写功能代码，遵循命名与错误处理规范
3. **Add Logging**: 为关键操作添加日志记录
4. **Write Tests**: 编写对应的单元测试
5. **Verify**: 运行测试，检查日志输出
6. **Update Checklist**: 标记任务为 `[x]` 完成

### When Blocked
- 如果 `things.py` API 不清晰 → 先编写测试脚本探索其行为
- 如果 Git 操作失败 → 检查仓库状态，记录详细错误信息
- 如果 Markdown 解析复杂 → 先实现简化版（全量重写），后续优化增量更新

### Safety Checks Before Each Commit
- [ ] 没有硬编码路径或凭证
- [ ] 所有异常都被捕获并记录
- [ ] Git 操作有超时保护
- [ ] 测试通过（如果有）

---

## Success Criteria

项目被视为成功，当：
1. ✅ 在 Things3 中创建任务后 2 秒内，GitHub 仓库出现对应 Markdown
2. ✅ 修改任务标题后，Git diff 仅显示该任务的标题行变更
3. ✅ 程序连续运行 7 天无崩溃，日志无 ERROR 级别记录
4. ✅ 全量校验能在 30 秒内完成（1000 任务规模）
5. ✅ launchd 服务开机自启动，无需人工干预

---

## Maintenance Notes

### Future Enhancements（未来增强）
- 支持双向同步（从 GitHub Markdown 反向更新 Things3）
- Web 界面查看同步状态
- 支持多设备冲突解决策略
- 导出为其他格式（Notion, Obsidian）

### Known Limitations
- Things3 数据库 schema 变化可能导致 `things.py` 失效（需定期更新依赖）
- 不支持 Things3 的附件同步（图片、文件）
- Git 推送失败时不会暂停监听（可能积累未提交变更）

---

**Generated by Technical PM & AI Architect | Ready for Codex Execution