# 使用手册

本手册面向首次部署 Things3 到 Git Markdown 同步服务的 macOS 用户。服务把 Things3 数据单向导出到一个本地 Git 工作树；不会反向修改 Things3。

## 1. 准备条件

准备两个不同的目录：

- **程序目录**：本项目的克隆目录，包含 `main.py` 和 `setup.py`。
- **目标仓库**：接收生成 Markdown 的已有 Git 工作树，也是 `REPO_PATH` 的值。

在开始前确认：

```bash
git -C /绝对路径/目标仓库 status
git -C /绝对路径/目标仓库 branch --show-current
```

目标仓库必须已有提交，且其当前分支必须与之后的 `GIT_BRANCH` 一致。若启用自动推送，还需要先在目标仓库中完成远端认证。

## 2. 安装程序

在程序目录执行：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

开发或运行自动化测试时，再安装：

```bash
python -m pip install -r requirements-dev.txt
```

## 3. 创建配置

推荐交互式创建配置：

```bash
python setup.py
```

输入目标仓库的本地绝对路径；出现自动推送提示时，直接按回车代表启用，输入 `n` 代表先只创建本地提交。脚本只会创建一次程序目录中的 `.env`；已有 `.env` 时不会覆盖。

也可以手动创建 `.env`：

```bash
cp .env.example .env
```

至少设置并核对以下值：

```dotenv
REPO_PATH=/绝对路径/目标仓库
AUTO_COMMIT=true
AUTO_PUSH=false
GIT_BRANCH=main
```

首次运行建议保持 `AUTO_PUSH=false`，检查生成结果与本地提交后再改为 `true`。`AUTO_PUSH=true` 必须同时设置 `AUTO_COMMIT=true`。

## 4. 首次前台同步

在程序目录并已激活虚拟环境时执行：

```bash
python main.py
```

启动后会立即读取完整快照、生成文件并按配置提交。随后程序继续监听数据库变化与定期完整同步。使用 `Control-C` 请求优雅停止；它会等待正在进行的同步与 watcher 清理完成。

首次运行后，在另一个终端检查目标仓库：

```bash
git -C /绝对路径/目标仓库 status
git -C /绝对路径/目标仓库 log --oneline -3
```

典型输出包括 `Inbox.md`、`Today.md`、`Projects/`、`Areas/`、`Archived/` 和 `.things3-sync-manifest.json`。生成的 Markdown 第一行带有 `generated-by: things3-github-sync` 标识。

## 5. 日常使用

Things3 数据库文件发生变化时，程序会对 `main.sqlite`、WAL 和 SHM 文件进行防抖，然后使用完整快照重新协调输出。没有业务变化时不会重写文件或创建新的同步提交。

不要手动编辑带生成标识的 Markdown 文件或清单。对没有该标识的陌生文件，协调器会保留而非覆盖或删除。删除的 Project/Area 在安全时会移至 `Archived/`，作为导出侧历史。

查看服务日志：

```bash
tail -f logs/sync.log
```

日志目录相对于程序目录，而不是目标仓库。

## 6. 启用自动推送

先确认目标仓库的远端和认证：

```bash
git -C /绝对路径/目标仓库 remote -v
git -C /绝对路径/目标仓库 push
```

确认无误后，将 `.env` 的 `AUTO_PUSH` 改为 `true`，停止并重新启动服务。推送失败不会丢失本地提交；程序会保存待推送状态，并在后续无变化同步时重试。

程序不会自动执行 `pull`、`merge` 或 `rebase`。远端超前或冲突时，请在目标仓库中手动处理，再恢复服务。

## 7. 生成 launchd 预览

生成项目内预览文件：

```bash
python generate_launchd.py --output build/com.things3githubsync.agent.plist
```

检查预览中的 `ProgramArguments`、`WorkingDirectory` 和日志路径。生成器不会改动系统 launchd。只有确认内容正确后，才显式安装：

```bash
cp build/com.things3githubsync.agent.plist ~/Library/LaunchAgents/com.things3githubsync.agent.plist
launchctl load ~/Library/LaunchAgents/com.things3githubsync.agent.plist
```

卸载时执行：

```bash
launchctl unload ~/Library/LaunchAgents/com.things3githubsync.agent.plist
```

launchd 的标准输出与错误输出位于 `logs/launchd.out.log` 和 `logs/launchd.err.log`。

## 8. 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 找不到 Things 数据库 | 设置 `THINGSDB` 为本机 `main.sqlite` 的绝对路径，或确认 Things3 数据目录存在。 |
| 数据库读取失败 | 为运行终端或 launchd 进程授予 macOS 隐私访问权限；等待 Things3 完成写入后重试。 |
| 配置启动失败 | 检查 `REPO_PATH` 是否存在、是否为 Git 工作树，以及 `GIT_BRANCH` 是否等于当前分支。 |
| Git 推送失败 | 在目标仓库手动检查远端、认证与远端状态；处理后重启或等待下一次同步。 |
| 清单格式错误 | 停止服务，检查 `.things3-sync-manifest.json`；恢复有效版本前不要批量删除生成文件。 |
| 退出等待较久 | 查看 `logs/sync.log`，服务会等待当前同步和 watcher 关闭。 |

## 9. 升级与验证

升级程序前先停止服务，再拉取代码和更新依赖：

```bash
git pull --ff-only
. .venv/bin/activate
python -m pip install -r requirements.txt
```

验证代码时运行：

```bash
python -m pytest tests -v
```

真实 Things3 访问、远端 Git 推送和 launchd 生命周期依赖本机环境，需由操作者在发布前单独确认。
