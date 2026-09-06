## [2026-09-03 23:42] 忽略 things.py 文件夹

- **需求/问题描述**：
  > 把 py 这个文件夹加入 Git ignore

- **实际实现的功能与改动**：
  - [忽略规则]：新增 `.gitignore`，忽略仓库根目录下的 `things.py/` 文件夹及其全部内容。
  - [测试/验证]：使用 `git check-ignore -v` 验证该目录已被 Git 忽略。

- **涉及文件**：
  - `.gitignore` (+1)
  - `docs/CHANGELOG.md` (+14)

- **Git 提交**：待创建

---

## [2026-09-06 23:27] 修复隔离提交失败时误推送

- **需求/问题描述**：
  > 继续完成 Things3 同步 MVP，并闭合 Task 7 的独立审查问题

- **实际实现的功能与改动**：
  - [Git 状态机修复]：明确区分无差异、提交成功和提交失败，隔离 index 早期失败或真实 index 刷新失败时不再误触发 pending push 重试。
  - [回归测试]：覆盖已有 pending push 引用与隔离提交早期失败同时出现时不得推送的场景。
  - [测试/验证]：Task 7 focused tests 13 passed，项目测试 86 passed。

- **涉及文件**：
  - `src/git_ops.py`
  - `tests/test_git_ops.py`

- **Git 提交**：待创建 `fix: prevent push after isolated commit failure`

---
