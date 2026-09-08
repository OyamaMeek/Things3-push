# HANDOFF20260906203616 development

> **Agent**: Claude Code · **Project**: /Users/oyamahappa/Documents/GitHub/Things3-push(main) · **Time**: 2026-09-06 20:58:54 – 2026-09-06 22:02:13 · **Messages**: 16 · **Tokens**: 259.6K

---

### 👤 User · 2026-09-06 20:58:54

根据 HANDOFF20260906203616.md继续开发

### 🤖 Assistant · 2026-09-06 20:58:58

Failed to authenticate. API Error: 401 无效的令牌 (request id: 202609061258572194619478268d9d65CJP98ja)

### 🤖 Assistant · 2026-09-06 21:02:22

No response requested.

### 👤 User · 2026-09-06 21:02:22

继续

### 🤖 Assistant · 2026-09-06 21:02:26

<details><summary>🧠 Thinking</summary>

**Inspecting handoff and repo**

</details>

我先读取交接文档和当前工作区状态，确认上次停在什么位置，再继续实现和验证。

<details><summary>🔧 Bash — git status --short --branch</summary>

Input:

```
{
  "command": "git status --short --branch",
  "description": "Show current branch and changes"
}
```

Output:

```
## main...origin/main
 ? .claude/worktrees/agent-a36ccd16e4f5b824a
 ? .claude/worktrees/agent-aa62f5662892e5e23
 ? .claude/worktrees/things3-sync-mvp-impl
```

</details>

<details><summary>🔧 Read — /Users/oyamahappa/Documents/GitHub/Things3-push/HANDOFF20260906203616.md</summary>

Input:

```
{
  "file_path": "/Users/oyamahappa/Documents/GitHub/Things3-push/HANDOFF20260906203616.md"
}
```

Output:

```
1	# Things3 Sync MVP 交接文档
2	
3	> 交接时间：2026-09-06 20:36:16
4	> 目标读者：没有本次会话上下文的新对话
5	
6	## 1. 我们在做什么
7	
8	当前项目是一个运行在 macOS 上的 Things3 -> Git Markdown 单向同步服务。目标数据流：
9	
10	```text
11	Things3 数据库（只读）
12	  -> things.py 读取接口
13	  -> 不可变 ThingsSnapshot
14	  -> 纯确定性 Markdown 渲染
15	  -> 原子文件协调与 manifest
16	  -> 临时 Git index 隔离提交/推送
17	  -> 用户指定的 Git 仓库
18	```
19	
20	MVP 设计和实施计划分别位于：
21	
22	- `docs/superpowers/specs/2026-09-04-things3-sync-mvp-design.md`
23	- `docs/superpowers/plans/2026-09-04-things3-sync-mvp.md`
24	
25	SDD 账本和所有任务 brief/report/review 位于：
26	
27	- `.superpowers/sdd/2026-09-04-things3-sync-mvp/progress.md`
28	
29	工作规则是按任务执行：每个任务先记录 BASE，派发 implementer，再做独立的 specification compliance 和 code quality review；有 Critical/Important finding 时由 implementer 修复，再做范围复审。
30	
31	## 2. 当前分支和工作区
32	
33	当前分支：`main`
34	
35	当前 HEAD：`b68f72b`（`origin/main` 同一提交）
36	
37	最近提交：
38	
39	```text
40	b68f72b 已按 macOS/POSIX 路径规则通过审查并记录
41	d4a17d7 feat: render deterministic task markdown
42	0d2a875 feat: render deterministic task markdown
43	487fab0 feat: read Things snapshots safely
44	abb26d5 feat: add sync models and configuration
45	45df0d6 docs: plan Things3 sync MVP
46	a839e1d docs: design Things3 sync MVP
47	564c30f first commit
48	```
49	
50	当前 `git status --short` 的重要状态：
51	
52	```text
53	M  src/renderer.py
54	M  tests/test_renderer.py
55	?? src/filesystem.py
56	?? src/git_ops.py
57	?? tests/test_filesystem.py
58	?? tests/test_git_ops.py
59	```
60	
61	另有以下已有嵌套 worktree 条目，属于既存隔离工作区，不是本次功能目标：
62	
63	```text
64	.claude/worktrees/agent-a36ccd16e4f5b824a
65	.claude/worktrees/agent-aa62f5662892e5e23
66	.claude/worktrees/things3-sync-mvp-impl
67	```
68	
69	`HANDOFF20260905060034.md` 也是既存未跟踪交接文件。不要删除、清理或重置上述内容。
70	
71	重要：当前 Task 4、Task 5/6、Task 7 的实现均未提交。不要假设它们已经进入 Git 历史；应先检查工作区，再分别完成审查和提交边界处理。
72	
73	## 3. 已完成内容
74	
75	### Task 1：模型和配置，已完成并 review clean
76	
77	提交：`abb26d5`
78	
79	主要文件：
80	
81	- `src/models.py`
82	- `src/config.py`
83	- `src/utils.py`
84	- `.env.example`
85	- `requirements.txt`
86	- `requirements-dev.txt`
87	- `tests/test_models.py`
88	- `tests/test_config.py`
89	
90	已实现：不可变 `ChecklistItem`、`TaskSnapshot`、`ContainerSnapshot`、`ThingsSnapshot`、`ContainerPath`、`RenderedSnapshot`、`ChangeSet`、`SyncResult`；配置解析/校验；路径清理和日志初始化。
91	
92	关键不变量：快照集合归一化为 tuple；`RenderedSnapshot.files` 是 `MappingProxyType`；重复 task/container UUID 被拒绝；状态只有 `incomplete`、`completed`、`canceled`；`AUTO_PUSH=true` 必须同时启用 `AUTO_COMMIT`。
93	
94	### Task 2：只读 Things 适配器，已完成并 review clean
95	
96	提交：`487fab0`
97	
98	主要文件：
99	
100	- `src/things_adapter.py`
101	- `tests/test_things_adapter.py`
102	
103	已实现：只使用 `todos`、`projects`、`areas`、`today`、`upcoming` 读取接口；显式数据库路径；现代 `ThingsData-*` 路径发现；完整快照重试；稀疏字典归一化；Today/Upcoming API 顺序保留并去重；不访问 SQLite 私有实现，不调用 mutation API。
104	
105	### Task 3：Markdown 合同，已完成并 review clean
106	
107	实现提交：`0d2a875`
108	
109	审查范围必须是 `487fab0..0d2a875`，不能用 `HEAD~1`，因为之后有不相关的 `d4a17d7`。
110	
111	主要文件：
112	
113	- `src/markdown.py`
114	- `tests/test_markdown.py`
115	
116	接口：`GENERATED_MARKER`、`escape_inline()`、`render_task()`、`render_document()`、`is_managed_markdown()`。
117	
118	已实现固定 marker、状态 checkbox、字段顺序、Markdown 特殊字符转义、CRLF/CR 处理、notes 缩进、tags、checklist UUID/完成时间、任务 separator 和 managed-file 检测。独立审查结论：specification compliance PASS，code quality PASS；测试 4 passed。证据：`task-3-review.md`。
119	
120	### Task 4：Snapshot Routing and Deterministic Rendering，代码完成并 review clean
121	
122	当前代码文件：
123	
124	- `src/renderer.py`
125	- `tests/conftest.py`
126	- `tests/test_renderer.py`
127	
128	接口：
129	
130	```python
131	render_snapshot(snapshot: ThingsSnapshot) -> RenderedSnapshot
132	allocate_container_paths(
133	    projects: Sequence[ContainerSnapshot],
134	    areas: Sequence[ContainerSnapshot],
135	) -> Tuple[ContainerPath, ...]
136	```
137	
138	已实现：
139	
140	- Project > Area > Inbox/Anytime/Someday 主路由；terminal status 先于 start-list。
141	- 固定七个顶层文件：`Inbox.md`、`Today.md`、`Anytime.md`、`Someday.md`、`Upcoming.md`、`已完成.md`、`已取消.md`。
142	- 每个 active Project/Area 即使为空也生成 `tasks.md`、`已完成.md`、`已取消.md`。
143	- 容器名称清理、大小写不敏感冲突处理、相同 UUID 前缀和 case-only UUID 的稳定消歧。
144	- UUID 派生路径 token 安全化，禁止 hostile UUID 产生绝对/`..` 路径。
145	- Today/Upcoming 严格按 snapshot 提供的 UUID 顺序，缺失 UUID warning 一次并跳过。
146	- 任务输入顺序不影响结果；普通任务稳定排序；终态按 `stop_date` 降序并保持确定性 tie-breaker。
147	- renderer 纯内存，不读写文件、不执行 Git、不访问 Things/SQLite。
148	
149	测试：renderer 12 passed；前序/项目测试合计在 Task 4 修复后 32 passed。Task 4 审查过程中发现并修复了两个 Important 问题：case-only UUID 路径冲突、UUID 派生路径未安全化。
150	
151	有一个审查项被明确裁定为不适用而停放：`sanitize_path_segment()` 不把反斜杠当 Windows 分隔符。用户选择本项目采用 macOS/POSIX-only 语义，因此标题中的反斜杠是普通字符。证据和裁定在 `task-4-rereview-round-2.md` 与 `progress.md`。
152	
153	### Task 5：Atomic File Reconciliation and Manifest，代码完成并 review clean
154	
155	当前实现和测试在：
156	
157	- `src/filesystem.py`
158	- `tests/test_filesystem.py`
159	
160	已实现：
161	
162	- `Manifest` frozen dataclass，version 1，严格顶层 schema。
163	- `.things3-sync-manifest.json` 安全读取、类型/版本/路径/UTF-8 校验。
164	- 所有 desired destination、祖先、manifest destination 在任何写入前做 ownership preflight。
165	- 直接文件、普通文件祖先、直接/祖先符号链接（包括悬空链接）均不能被静默替换。
166	- sibling temporary file、UTF-8、LF、flush、fsync、`os.replace()` 和 finally 清理。
167	- 内容未变化不重写；manifest 最后写入。
168	- 只删除旧 manifest 明确管理且仍带生成 marker 的 Markdown；陌生文件保留并 warning。
169	- 只沿已知容器目录做非递归空目录清理。
170	- `ChangeSet` 返回确定性 added/modified/deleted，并把历史 managed paths、当前 managed paths、manifest 和变更路径放入明确 `git_paths`。
171	
172	Task 5 审查经历三轮修复：
173	
174	1. 补齐普通文件祖先预检、严格 manifest schema、非 UTF-8 unowned destination 异常。
175	2. 补齐直接/祖先符号链接预检、非法 UTF-8 manifest 的 `ValueError`。
176	3. 补齐 manifest 本身悬空符号链接预检。
177	
178	最终 specification compliance PASS、code quality PASS；文件系统测试 23 passed，项目测试当时 55 passed。证据：`task-5-rereview-round-3.md`。
179	
180	### Task 6：Container Rename and Persistent Archive Behavior，代码完成并 review clean
181	
182	Task 6 修改了同一个 `src/filesystem.py` 和 `tests/test_filesystem.py`，当前仍未提交。
183	
184	已实现：
185	
186	- 按 `<kind>:<uuid>` 识别 active container。
187	- active rename 只写新路径并删除旧路径下标记的 managed 文件，不移动整个目录。
188	- 消失的 Project/Area 分别归档到 `Archived/Projects`、`Archived/Areas`。
189	- 归档目录使用最后 active 名称和稳定八字符 UUID 后缀；全非字母数字 UUID 使用 SHA-256 前缀。
190	- archive mapping 持久化；重新出现保留历史；再次消失复用同一 archive 目录。
191	- 陌生文件始终保留并记录 warning；归档文件也做 marker/ownership 检查。
192	- 归档路径经过相对路径和仓库 containment 校验；不用 `shutil.move` 或递归目录移动。
193	
194	测试：文件系统测试 32 passed；项目测试 64 passed。独立审查：specification compliance PASS，code quality PASS with two deferred Minor findings：
195	
196	- `_remove_empty_container_directories()` 对某些 unchanged/nonempty active container 可能记录误导性 warning。
197	- `active_previous_paths` 变量计算后未使用。
198	
199	这两个 Minor 已登记在 `progress.md`，未进入修复循环；最终 whole-branch review 时需要重新判断是否清理。
200	
201	### Task 7：Explicit-Path Git Operations，已实现但正式 review 未完成
202	
203	当前文件：
204	
205	- `src/git_ops.py`
206	- `tests/test_git_ops.py`
207	
208	已实现：
209	
210	- `GitClient` 统一 subprocess 边界，所有调用带 `cwd`、`capture_output=True`、`text=True`、timeout、`check=False`。
211	- `git add -- <明确路径>`，没有 `git add .`。
212	- URL userinfo 和 `token=`、`auth-token=`、`password=` 日志脱敏。
213	- 临时 `GIT_INDEX_FILE`，`read-tree HEAD`，仅暂存 managed paths，使用实际 `--name-status -z` 统计 commit。
214	- commit 成功后只用 managed path 刷新真实 index，保留用户无关 staged changes。
215	- `refs/things3-sync/pending-push` 的创建、推送失败重试、成功清除。
216	- 不自动 pull、merge、rebase。
217	
218	测试：Task 7 focused 12 passed；当时项目测试 76 passed；`py_compile` 和 `git diff --check` 通过。证据：`task-7-report.md`。
219	
220	卡点：Task 7 formal independent review 尚未完成。第一次 review agent 因 API 503 失败，第二次尝试因 token quota 不足返回 403；因此没有 `task-7-review.md`，不能把 Task 7 标记为 review clean，也不能直接进入 Task 8。
221	
222	## 4. 当前卡点
223	
224	唯一明确的流程卡点是 Task 7 的正式 SDD review gate。
225	
226	必须先完成：
227	
228	1. 阅读 `task-7-brief.md`、`task-7-report.md`、`review-task-7-complete.diff`。
229	2. 重新派发独立 reviewer，要求分别输出 specification compliance 和 code quality verdict。
230	3. 如果出现 Critical/Important finding，恢复 Task 7 implementer（前 3 轮）或派发新 implementer 修复，不能由 controller 直接编辑 `src/git_ops.py`。
231	4. 每轮修复后生成 scoped review package 并独立复审，最多 5 轮。
232	5. 只有 review clean 后才能在 `progress.md` 追加 Task 7 complete。
233	
234	审查代理可优先使用更低成本模型以避开当前额度问题，但仍必须是独立 reviewer，不能把实现代理自测当正式审查。
235	
236	## 5. 下一步计划
237	
238	### 第一步：闭合 Task 7 review
239	
240	- 保持当前工作区内容不变，先验证 `git status --short`。
241	- 使用完整未跟踪文件内容重新生成 Task 7 review package，不能只依赖 `git diff`，因为新文件尚未 tracked。
242	- 独立 review Git subprocess 边界、临时 index 隔离、路径规格、凭证脱敏、pending-push 状态机和真实临时仓库测试。
243	- 修复 findings 后复审，更新 SDD ledger。
244	
245	### 第二步：Task 7 边界检查和提交准备
246	
247	Task 7 review clean 后，分别检查各任务的未提交内容。由于 Task 4、Task 5/6、Task 7 都在当前 workspace，不能使用 `git add .`。
248	
249	计划提交前应：
250	
251	- 先确认用户是否希望现在创建功能提交；本会话之前明确要求实现代理不自行提交。
252	- 若提交，按任务拆分、显式列出路径并使用 `git commit --only`；不要把 `HANDOFF*`、nested worktree 条目、`.DS_Store`、`.gitignore` 或其他无关状态带入。
253	- 提交前检查 `git status --short`、`git diff --cached --name-status`、`git show --name-status HEAD`。
254	
255	### 第三步：Task 8 — Sync Engine Transaction Boundary
256	
257	按计划文件生成 brief 并记录新的 BASE，然后只新增：
258	
259	- `src/sync_engine.py`
260	- `tests/test_sync_engine.py`
261	
262	实现读取 -> render -> reconcile -> Git 的单一路径、进程内互斥锁、`sync_if_idle()` 非阻塞入口、失败边界和 `SyncResult`。完成后执行独立 spec/code-quality review。
263	
264	后续顺序：
265	
266	- Task 9：SQLite/WAL/SHM watcher、防抖、pending rerun。
267	- Task 10：service lifecycle、启动/周期同步、SIGINT/SIGTERM。
268	- Task 11：setup.py 和 launchd plist preview。
269	- Task 12：临时 Git 仓库端到端集成测试。
270	- Task 13：README 与 Agent.md 对齐。
271	- Task 14：compileall、全套测试、禁止操作扫描、whole-branch review。
272	
273	每个任务必须有 brief、记录 BASE、implementer report、review package 和独立双 verdict review。
274	
275	## 6. 绝对不要踩的坑
276	
277	### Git 和分支
278	
279	- 当前在 `main`，不要擅自新建嵌套 worktree，也不要切换到旧实现 worktree。
280	- 不要 `git reset --hard`、rebase、amend、force push、删除分支或清理工作区。
281	- 不要使用 `git clean -fdx`，尤其不能清理 `.superpowers/sdd/`、`.claude/worktrees/` 或 `.DS_Store`。
282	- 不要使用 `git add .` 或不带明确路径的 commit。
283	- 不要把无关的 `.gitignore`、`docs/CHANGELOG.md`、`.DS_Store`、HANDOFF 文件或 nested worktree 状态带入功能提交。
284	- 不要把 `HEAD~1` 当 task review BASE；必须使用实际 dispatch 前记录的 BASE。
285	- 未经用户明确要求，不要 push、创建 PR、修改远程或加载 launchd。
286	
287	### SDD 流程
288	
289	- implementer 自测不是正式 review；正式 review 必须分别给出规格合规和代码质量 verdict。
290	- reviewer 的 Critical/Important finding 必须进入修复循环；controller 不直接修改相关实现。
291	- 修复后必须重新生成 scoped package 和独立复审，不能因改动很小而跳过。
292	- Minor finding 不能静默丢弃；应记录为 deferred 或修复。
293	- review agent 失败后不要虚构结论；重新派发并记录真实原因。
294	- 未完成 Task 7 review 前不能开始 Task 8。
295	
296	### Things3 只读边界
297	
298	- 业务代码只能通过 `things.py` 的窄读取接口访问 Things。
299	- 不要读取/写入 Things SQLite 私有 schema。
300	- 不要导入或调用 `complete()`、`url()` mutation helper。
301	- 不要构造 `update`、`update-project` 或其他写入 URL。
302	- 不要把 `things.py` 文档中的 `Task`、`Project`、`Area` 当作公共类。
303	- 不要把 `trashed` 自动映射为 canceled。
304	- 不要输出公开 API 无法可靠提供的 priority、Evening、附件或重复规则字段。
305	- Today 必须复用 `things.today()` 语义；不能只根据 `start` 字段自行重建。
306	- 完整快照读取成功之前，不得修改目标仓库或运行 Git。
307	
308	### 文件系统和路径
309	
310	- 生产文件操作使用 `pathlib.Path`。
311	- 写文件必须使用同目录临时文件、flush、fsync、`os.replace()`；失败时保留原文件。
312	- 任何 desired destination、祖先、manifest destination 在写入前都要做 ownership preflight。
313	- 绝不能替换未标记陌生文件或符号链接；悬空符号链接也算已存在的 unowned entry。
314	- manifest 必须严格按 version 1 schema 校验；坏 JSON、坏 UTF-8、错误类型、未知字段、危险路径都要在任何写入前失败。
315	- 只删除 marker/manifest 明确管理的文件；陌
… (truncated)
```

</details>

<details><summary>🔧 Bash — rg --files -g 'CLAUDE.md' -g '!node_modules' -g '!vendor'</summary>

Input:

```
{
  "command": "rg --files -g 'CLAUDE.md' -g '!node_modules' -g '!vendor'",
  "description": "Find repository instructions"
}
```

Output:

```
(Bash completed with no output)
```

</details>

<details><summary>🔧 Bash — git log --oneline -8</summary>

Input:

```
{
  "command": "git log --oneline -8",
  "description": "Show recent commits"
}
```

Output:

```
242aa2b add:HANDOFF20260906203616.md
b68f72b 已按 macOS/POSIX 路径规则通过审查并记录
d4a17d7 feat: render deterministic task markdown
0d2a875 feat: render deterministic task markdown
487fab0 feat: read Things snapshots safely
abb26d5 feat: add sync models and configuration
45df0d6 docs: plan Things3 sync MVP
a839e1d docs: design Things3 sync MVP
```

</details>

### 🤖 Assistant · 2026-09-06 21:02:34

Failed to authenticate. API Error: 401 无效的令牌 (request id: 202609061302334098768208268d9d6AfK1ld37)

### 🤖 Assistant · 2026-09-06 21:04:11

No response requested.

### 👤 User · 2026-09-06 21:04:11

继续

### 🤖 Assistant · 2026-09-06 21:04:21

<details><summary>🧠 Thinking</summary>

**Inspecting Agent.md specs for review**

</details>

当前主分支没有未提交功能文件，交接文档描述的 Task 7 内容位于嵌套工作区；我先核对项目规则、Task 7 brief/report 和实际文件位置，再按既定 review gate 继续。

<details><summary>🔧 Bash — rg --files -g 'Agent.md' -g 'docs/superpowers/specs/**' -g 'docs/superpowers/plans/**' -g '.superpowers/sdd/**' -g 'task-7-brief.md' -g 'task-7-report.md' -g 'review-task-7-complete.diff' -g 'src/git_…</summary>

Input:

```
{
  "command": "rg --files -g 'Agent.md' -g 'docs/superpowers/specs/**' -g 'docs/superpowers/plans/**' -g '.superpowers/sdd/**' -g 'task-7-brief.md' -g 'task-7-report.md' -g 'review-task-7-complete.diff' -g 'src/git_ops.py' -g 'tests/test_git_ops.py'",
  "description": "Locate project docs and Task 7 files"
}
```

Output:

```
src/git_ops.py
docs/superpowers/specs/2026-09-04-things3-sync-mvp-design.md
docs/superpowers/plans/2026-09-04-things3-sync-mvp.md
tests/test_git_ops.py
Agent.md
```

</details>

<details><summary>🔧 Read — /Users/oyamahappa/Documents/GitHub/Things3-push/Agent.md</summary>

Input:

```
{
  "file_path": "/Users/oyamahappa/Documents/GitHub/Things3-push/Agent.md"
}
```

Output:

```
1	```markdown
2	# AGENTS.md - Things3 to GitHub Markdown Sync Agent
3	
4	## Project Overview & Architecture
5	
6	### Core Mission
7	自动监听 Things3 数据库变化，实时将任务数据转换为结构化 Markdown 文件，并通过 Git 同步到 GitHub 仓库，保持任务管理数据的版本化备份与可读性。
8	
9	### Key Business Entities
10	- **Task（任务）**: Things3 核心实体，包含标题、状态、元数据、子任务
11	- **Project（项目）**: 任务容器，有独立文件夹结构
12	- **Area（领域）**: 更高层级的任务分组
13	- **Tag（标签）**: 跨项目的任务分类标记
14	
15	### Core Data Flow
16	```
17	Things3 SQLite DB 
18	  ↓ (watchdog 监听文件变化)
19	things.py 库解析
20	  ↓ (数据模型转换)
21	Markdown Generator (增量更新策略)
22	  ↓ (文件系统写入)
23	Git Operations (auto commit & push)
24	  ↓
25	GitHub Repository (远程备份)
26	```
27	
28	### Architecture Principles
29	- **事件驱动**: 文件监听 + 信号处理
30	- **增量优先**: 精确定位修改，减少 Git diff 噪音
31	- **容错设计**: 重试机制 + 日志追踪 + 全量校验兜底
32	- **零人工干预**: 后台服务 + 自动初始化
33	
34	---
35	
36	## Tech Stack & Dependencies
37	
38	### Runtime Environment
39	- **OS**: macOS 10.14+（Things3 限定）
40	- **Python**: 3.6+ (推荐 3.9+)
41	- **Git**: 2.20+（系统命令行）
42	
43	### Core Dependencies
44	```
45	things.py>=0.2.0        # Things3 数据库接口
46	watchdog>=2.1.0         # 文件系统监听
47	python-dotenv>=0.19.0   # 环境配置管理
48	```
49	
50	### System Integration
51	- **launchd**: macOS 后台服务守护进程
52	- **Things3 数据库路径**: `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/Things Database.thingsdatabase/main.sqlite`
53	
54	---
55	
56	## Directory Structure & Conventions
57	
58	### Project Structure
59	```
60	things3-github-sync/
61	├── .env                      # 配置文件（Git ignore）
62	├── .env.example              # 配置模板
63	├── requirements.txt          # Python 依赖
64	├── README.md                 # 用户文档
65	├── setup.py                  # 交互式初始化脚本
66	├── generate_launchd.py       # launchd plist 生成器
67	├── main.py                   # 主程序入口
68	├── src/
69	│   ├── __init__.py
70	│   ├── watcher.py            # 文件监听模块
71	│   ├── parser.py             # Things3 数据解析（基于 things.py）
72	│   ├── markdown_generator.py # Markdown 生成与增量更新
73	│   ├── git_ops.py            # Git 命令封装
74	│   ├── sync_engine.py        # 核心同步逻辑协调器
75	│   ├── validator.py          # 全量对比校验模块
76	│   └── utils.py              # 工具函数（文件名清理、日志等）
77	├── logs/                     # 日志目录（自动创建）
78	└── tests/                    # 单元测试（可选）
79	```
80	
81	### Target Repository Structure（GitHub 仓库本地路径）
82	```
83	<REPO_PATH>/
84	├── Inbox.md
85	├── Today.md
86	├── Anytime.md
87	├── Someday.md
88	├── Upcoming.md
89	├── 已完成.md
90	├── 已取消.md
91	├── Projects/
92	│   ├── 项目A/
93	│   │   ├── tasks.md
94	│   │   ├── 已完成.md
95	│   │   └── 已取消.md
96	│   └── 项目B/
97	│       └── tasks.md
98	├── Areas/
99	│   ├── 工作/
100	│   │   ├── tasks.md
101	│   │   ├── 已完成.md
102	│   │   └── 已取消.md
103	│   └── 个人/
104	│       └── tasks.md
105	└── Archived/                 # 已归档的 Project/Area
106	    └── 旧项目/
107	```
108	
109	### Markdown Format Standard
110	```markdown
111	## [ ] 任务标题
112	<!-- uuid: ABC123DEF456 -->
113	- **创建时间**: 2025-01-15 10:30
114	- **修改时间**: 2025-01-15 14:20
115	- **开始日期**: 2025-01-16
116	- **截止日期**: 2025-01-20
117	- **标签**: #工作 #重要
118	- **优先级**: High
119	- **特殊字段**: Evening
120	- **备注**: 
121	  任务的详细描述内容，支持多行
122	- **子任务**:
123	  - [ ] 子任务1 <!-- uuid: SUB123 -->
124	  - [x] 子任务2 <!-- uuid: SUB456 -->
125	
126	---
127	```
128	
129	### Naming Conventions
130	- **文件名清理**: 非法字符 (`/`, `:`, `?`, `*`, `<`, `>`, `|`, `"`) 替换为 `-`
131	- **UUID 注释**: 每个任务/子任务包含隐藏的 `<!-- uuid: xxx -->` 用于增量定位
132	- **状态标记**: `[ ]` 未完成, `[x]` 已完成, `[-]` 已取消
133	
134	---
135	
136	## Codex Operational Rules
137	
138	### Pre-execution Checklist
139	在修改任何核心逻辑前，必须先读取并理解：
140	1. `.env` 配置文件格式（通过 `.env.example` 了解）
141	2. `things.py` 库的 API 文档（Task, Project, Area 对象结构）
142	3. 现有 Markdown 文件的格式约定（UUID 注释位置）
143	4. Git 仓库的当前状态（避免破坏现有提交）
144	
145	### Coding Constraints
146	
147	#### 严格禁止
148	- ❌ 直接修改 Things3 数据库（只读访问）
149	- ❌ 在 Markdown 中硬编码文件路径或用户信息
150	- ❌ 使用 `git add .`（必须明确指定文件）
151	- ❌ 引入未在 `requirements.txt` 声明的第三方库
152	- ❌ 阻塞式等待（所有 I/O 操作需配置超时）
153	
154	#### 必须遵守
155	- ✅ 所有文件操作使用 `pathlib.Path`
156	- ✅ Git 命令通过 `subprocess.run()` 执行，捕获 stderr
157	- ✅ 数据库读取失败时，等待 10 秒重试，最多 3 次
158	- ✅ 每个函数配置日志记录（使用 `logging` 模块）
159	- ✅ 信号处理：捕获 `SIGINT`, `SIGTERM` 优雅退出
160	
161	#### Error Handling Standard
162	```python
163	import logging
164	import subprocess
165	from pathlib import Path
166	
167	def safe_git_operation(repo_path: Path, command: list) -> bool:
168	    """
169	    执行 Git 命令，记录错误但不中断主流程
170	  
171	    Returns:
172	        bool: 操作是否成功
173	    """
174	    try:
175	        result = subprocess.run(
176	            command,
177	            cwd=repo_path,
178	            capture_output=True,
179	            text=True,
180	            timeout=30,
181	            check=True
182	        )
183	        logging.info(f"Git command success: {' '.join(command)}")
184	        return True
185	    except subprocess.CalledProcessError as e:
186	        logging.error(f"Git command failed: {e.stderr}")
187	        return False
188	    except subprocess.TimeoutExpired:
189	        logging.error(f"Git command timeout: {' '.join(command)}")
190	        return False
191	```
192	
193	### Testing & Verification
194	
195	#### Unit Test Requirements
196	- `tests/test_markdown_generator.py`: 测试 UUID 注释插入、任务章节定位
197	- `tests/test_parser.py`: 验证 Things3 数据解析的边界情况（空任务、特殊字符）
198	- `tests/test_git_ops.py`: Mock Git 命令，测试提交信息生成逻辑
199	
200	#### Integration Test Scenarios
201	1. 创建任务 → 验证 Markdown 生成 → 检查 Git commit
202	2. 修改任务标题 → 验证仅该行被修改（Git diff 精确）
203	3. 移动任务（Inbox → Project）→ 验证旧文件删除 + 新文件创建
204	4. 删除 Project → 验证文件夹移动到 `Archived/`
205	
206	---
207	
208	## Verification Commands
209	
210	### Environment Setup
211	```bash
212	# 创建虚拟环境
213	python3 -m venv venv
214	source venv/bin/activate
215	
216	# 安装依赖
217	pip install -r requirements.txt
218	
219	# 交互式初始化（生成 .env 和 launchd plist）
220	python setup.py
221	```
222	
223	### Development Workflow
224	```bash
225	# 运行主程序（前台测试）
226	python main.py
227	
228	# 检查日志
229	tail -f logs/sync_$(date +%Y-%m-%d).log
230	
231	# 手动触发全量校验（调试用）
232	python -c "from src.validator import full_sync; full_sync()"
233	```
234	
235	### Production Deployment
236	```bash
237	# 生成 launchd plist
238	python generate_launchd.py
239	
240	# 加载服务
241	launchctl load ~/Library/LaunchAgents/com.things3sync.plist
242	
243	# 查看服务状态
244	launchctl list | grep things3sync
245	
246	# 卸载服务
247	launchctl unload ~/Library/LaunchAgents/com.things3sync.plist
248	```
249	
250	### Code Quality Checks
251	```bash
252	# 代码格式化（推荐 black）
253	black src/ --line-length 100
254	
255	# 类型检查（可选）
256	mypy src/ --ignore-missing-imports
257	
258	# 运行测试
259	pytest tests/ -v --cov=src
260	```
261	
262	---
263	
264	## Configuration Specification
265	
266	### .env File Format
267	```bash
268	# GitHub 仓库本地路径（已 clone 并配置认证）
269	REPO_PATH=/Users/username/Documents/things-backup
270	
271	# 日志配置
272	LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
273	LOG_MAX_BYTES=10485760  # 10MB
274	LOG_BACKUP_COUNT=5
275	
276	# 监听配置
277	WATCH_DEBOUNCE_SECONDS=2  # 防抖延迟（可选，默认立即提交）
278	
279	# 全量校验间隔（秒）
280	FULL_SYNC_INTERVAL=3600  # 每小时一次
281	```
282	
283	### .env.example Template
284	```bash
285	REPO_PATH=/path/to/your/github/repo
286	LOG_LEVEL=INFO
287	LOG_MAX_BYTES=10485760
288	LOG_BACKUP_COUNT=5
289	FULL_SYNC_INTERVAL=3600
290	```
291	
292	---
293	
294	## Phased Roadmap & Task Checklist
295	
296	### Phase 1: Core Infrastructure（核心基础设施）
297	- [ ] **Task 1.1**: 创建项目目录结构，初始化 Git 仓库
298	- [ ] **Task 1.2**: 编写 `requirements.txt`，包含 `things.py`, `watchdog`, `python-dotenv`
299	- [ ] **Task 1.3**: 实现 `src/utils.py` 
300	  - 文件名清理函数 `sanitize_filename(name: str) -> str`
301	  - 日志初始化函数 `setup_logging(log_dir: Path, level: str)`
302	  - UUID 生成与注释解析函数
303	- [ ] **Task 1.4**: 编写 `.env.example` 模板
304	
305	### Phase 2: Things3 Data Access（数据访问层）
306	- [ ] **Task 2.1**: 实现 `src/parser.py`
307	  - 封装 `things.py` 接口，提供统一数据模型
308	  - 函数：`get_all_tasks()`, `get_task_by_uuid()`, `get_projects()`, `get_areas()`
309	  - 处理已完成/已取消任务的过滤逻辑
310	- [ ] **Task 2.2**: 添加数据库读取重试机制（10 秒 × 3 次）
311	- [ ] **Task 2.3**: 编写 `tests/test_parser.py` 测试边界情况
312	
313	### Phase 3: Markdown Generation Engine（Markdown 生成引擎）
314	- [ ] **Task 3.1**: 实现 `src/markdown_generator.py` 基础版
315	  - 函数：`generate_task_markdown(task) -> str`
316	  - 包含 UUID 注释、所有元数据字段、子任务嵌套列表
317	- [ ] **Task 3.2**: 实现增量更新逻辑
318	  - 函数：`update_task_in_file(file_path: Path, task_uuid: str, new_content: str)`
319	  - 通过正则表达式定位 `<!-- uuid: xxx -->` 章节
320	  - 精确替换该章节内容，保留文件其他部分
321	- [ ] **Task 3.3**: 实现文件结构管理
322	  - 函数：`get_task_file_path(task) -> Path` 根据任务类型返回正确路径
323	  - 处理 Inbox/Today/Anytime/Someday/Projects/Areas 的路径映射
324	- [ ] **Task 3.4**: 实现任务删除逻辑
325	  - 函数：`remove_task_from_file(file_path: Path, task_uuid: str)`
326	- [ ] **Task 3.5**: 编写 `tests/test_markdown_generator.py`
327	
328	### Phase 4: Git Operations（Git 操作层）
329	- [ ] **Task 4.1**: 实现 `src/git_ops.py`
330	  - 函数：`git_add(repo_path: Path, files: list)`
331	  - 函数：`git_commit(repo_path: Path, message: str) -> bool`
332	  - 函数：`git_push(repo_path: Path) -> bool`
333	  - 所有操作包含错误处理和日志记录
334	- [ ] **Task 4.2**: 实现智能 commit message 生成
335	  - 函数：`generate_commit_message(changes: dict) -> str`
336	  - 格式：`Update: 2025-01-15 10:30 | Added 3, Modified 2, Deleted 1`
337	- [ ] **Task 4.3**: 编写 `tests/test_git_ops.py`（使用 Mock）
338	
339	### Phase 5: Sync Engine（同步引擎）
340	- [ ] **Task 5.1**: 实现 `src/sync_engine.py` 核心协调器
341	  - 函数：`sync_changes(changed_tasks: list)`
342	  - 逻辑：解析任务 → 生成/更新 Markdown → Git 提交
343	- [ ] **Task 5.2**: 实现任务移动检测
344	  - 通过比对任务当前路径与 Markdown 文件位置
345	  - 删除旧位置章节 + 新位置创建
346	- [ ] **Task 5.3**: 实现 Project/Area 归档逻辑
347	  - 检测已删除的容器 → 移动文件夹到 `Archived/`
348	- [ ] **Task 5.4**: 实现动态视图（Today/Upcoming）更新
349	  - 每次全量重新生成 `Today.md`（只包含当天任务）
350	  - `Upcoming.md` 基于日期范围过滤
351	
352	### Phase 6: File Watcher（文件监听）
353	- [ ] **Task 6.1**: 实现 `src/watcher.py`
354	  - 使用 `watchdog` 监听 Things3 SQLite 文件
355	  - 触发 `sync_engine.sync_changes()`
356	- [ ] **Task 6.2**: 添加监听中断检测
357	  - 如果全量校验正在进行 → 中断并重新开始
358	- [ ] **Task 6.3**: 实现优雅退出
359	  - 捕获 `SIGINT`, `SIGTERM` → 完成当前 Git 操作 → 退出
360	
361	### Phase 7: Full Sync Validator（全量校验）
362	- [ ] **Task 7.1**: 实现 `src/validator.py`
363	  - 函数：`full_sync_validation(repo_path: Path)`
364	  - 遍历 Things3 所有任务 → 比对本地 Markdown
365	  - 缺失任务 → 生成；多余章节 → 删除；不一致 → 覆盖
366	- [ ] **Task 7.2**: 集成定时触发（每小时一次）
367	  - 使用 `threading.Timer` 或 `schedule` 库
368	- [ ] **Task 7.3**: 校验完成后生成特殊 commit
369	  - Message: `Full sync verification: 2025-01-15 14:00`
370	
371	### Phase 8: Interactive Setup（交互式初始化）
372	- [ ] **Task 8.1**: 编写 `setup.py` 交互式配置脚本
373	  - 询问：GitHub 仓库本地路径
374	  - 验证路径存在且为 Git 仓库
375	  - 生成 `.env` 文件
376	- [ ] **Task 8.2**: 编写 `generate_launchd.py`
377	  - 读取 `.env` 中的路径
378	  - 生成 `~/Library/LaunchAgents/com.things3sync.plist`
379	  - 自动替换脚本路径、Python 解释器路径
380	- [ ] **Task 8.3**: 提供 launchd plist 模板
381	  ```xml
382	  <?xml version="1.0" encoding="UTF-8"?>
383	  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
384	  <plist version="1.0">
385	  <dict>
386	      <key>Label</key>
387	      <string>com.things3sync</string>
388	      <key>ProgramArguments</key>
389	      <array>
390	          <string>/path/to/venv/bin/python</string>
391	          <string>/path/to/main.py</string>
392	      </array>
393	      <key>RunAtLoad</key>
394	      <true/>
395	      <key>KeepAlive</key>
396	      <true/>
397	      <key>StandardOutPath</key>
398	      <string>/path/to/logs/launchd.out.log</string>
399	      <key>StandardErrorPath</key>
400	      <string>/path/to/logs/launchd.err.log</string>
401	  </dict>
402	  </plist>
403	  ```
404	
405	### Phase 9: Main Entry Point（主入口）
406	- [ ] **Task 9.1**: 编写 `main.py`
407	  - 加载 `.env` 配置
408	  - 初始化日志系统
409	  - 启动文件监听
410	  - 启动全量校验定时器
411	  - 注册信号处理器
412	- [ ] **Task 9.2**: 添加启动时首次全量同步
413	  - 确保程序启动时数据一致
414	
415	### Phase 10: Documentation & Testing（文档与测试）
416	- [ ] **Task 10.1**: 编写 `README.md` 用户文档
417	  - 安装步骤
418	  - 配置说明
419	  - 故障排查指南
420	- [ ] **Task 10.2**: 运行完整集成测试
421	  - 创建测试 Things3 任务 → 验证同步
422	  - 修改任务 → 验证 Git diff 精确性
423	  - 删除任务 → 验证 Markdown 清理
424	- [ ] **Task 10.3**: 性能测试
425	  - 1000+ 任务场景下的同步延迟
426	  - 全量校验耗时测试
427	
428	### Phase 11: Edge Cases & Polish（边界情况与优化）
429	- [ ] **Task 11.1**: 处理极端情况
430	  - 任务标题超长（截断或换行）
431	  - 任务标题包含 Markdown 特殊字符（转义）
432	  - 空 Project/Area（保留文件夹结构）
433	- [ ] **Task 11.2**: Git 冲突处理
434	  - 如果远程有更新 → 先 pull 再 push（可选）
435	- [ ] **Task 11.3**: 添加性能监控
436	  - 每次同步耗
… (truncated)
```

</details>

<details><summary>🔧 Read — /Users/oyamahappa/Documents/GitHub/Things3-push/docs/superpowers/specs/2026-09-04-things3-sync-mvp-design.md</summary>

Input:

```
{
  "file_path": "/Users/oyamahappa/Documents/GitHub/Things3-push/docs/superpowers/specs/2026-09-04-things3-sync-mvp-design.md"
}
```

Output:

```
1	# Things3 到 GitHub Markdown 同步 MVP 设计
2	
3	## 背景
4	
5	本项目需要在 macOS 上只读监听 Things3 数据库，将任务导出为结构化 Markdown，并通过 Git 自动提交和推送到用户已配置的远端仓库。
6	
7	仓库中的 `Agent.md` 描述了完整产品愿景，但当前主项目尚无实现。内嵌的 `things.py` 1.0.1 参考库公开的是返回稀疏字典的函数接口，而不是 `Task`、`Project`、`Area` 类；它也不提供优先级、Evening 等字段。因此 MVP 以参考库的真实只读数据为准，不输出无法可靠获得的字段。
8	
9	## 目标
10	
11	MVP 必须做到：
12	
13	1. 启动时读取完整 Things3 快照并同步 Markdown。
14	2. 监听 Things3 SQLite 数据库及其 WAL/SHM 变化，经防抖后再次同步。
15	3. 使用确定性渲染和原子文件替换，使内容未变化时不写磁盘、不产生 Git diff。
16	4. 自动暂存同步器实际变更的明确路径，按配置提交并推送。
17	5. 定时运行同一套完整快照同步，修复遗漏或漂移。
18	6. 捕获 `SIGINT` 和 `SIGTERM`，停止接收新工作并等待当前同步结束。
19	7. 提供安装、配置、前台运行与 launchd 部署文档和自动化测试。
20	
21	## 非目标
22	
23	MVP 不包括：
24	
25	- 从 Markdown 写回 Things3。
26	- Things 附件同步。
27	- 自动 merge、rebase 或解决 Git 冲突。
28	- 从底层数据库私有字段推导 `things.py` 未公开的优先级、Evening 或重复规则。
29	- Web 管理界面和性能监控面板。
30	- 对真实 GitHub 远端或真实用户 Things 数据库执行自动化集成测试。
31	
32	## 关键决策
33	
34	### 同步策略
35	
36	采用“防抖后的确定性完整快照”策略，而不是在 MVP 中维护独立的增量写入路径。
37	
38	每次同步均执行：
39	
40	```text
41	读取完整只读快照
42	  -> 规范化数据
43	  -> 渲染期望文件集合
44	  -> 原子协调磁盘
45	  -> 明确暂存变更路径
46	  -> 可选提交
47	  -> 可选推送
48	```
49	
50	SQLite 文件变化事件无法直接指出发生变化的任务。即使做 UUID 级增量更新，也必须先读取新快照做差异比较。完整快照渲染可同时正确处理任务移动、删除、容器重命名和 Today/Upcoming 派生视图，并让启动同步、监听同步和定时校验复用同一条代码路径。
51	
52	完整快照不意味着无条件重写文件。文件协调器先比较字节内容，只替换发生变化的文件。由此，单个标题变化通常只产生对应标题行的 Git diff。
53	
54	### 文件所有权
55	
56	同步器完全管理它生成的 Markdown 内容，但删除操作采用保守边界：
57	
58	- 每个生成文件包含稳定的生成标识。
59	- 仅删除位于已知导出路径中、带生成标识且不再属于期望快照的文件。
60	- 未带生成标识的陌生文件始终保留并记录警告。
61	- 同步器不使用笼统的目录递归删除处理未知内容。
62	
63	该规则兼顾确定性全量协调和用户文件保护。
64	
65	### 主位置与派生视图
66	
67	每个任务只有一个主位置，优先级如下：
68	
69	1. 所属 Project。
70	2. 所属 Area。
71	3. `Inbox`、`Anytime` 或 `Someday` 顶层列表。
72	
73	`Today.md` 和 `Upcoming.md` 是派生视图，允许重复展示已有主位置的任务。Today 的语义直接复用 `things.today()`，不根据单一 `start` 字段自行重建。
74	
75	## 架构
76	
77	### `src/config.py`
78	
79	负责读取和验证 `.env` 配置，向其他模块提供类型化配置对象。配置包括：
80	
81	- `REPO_PATH`：目标 Git 仓库绝对路径。
82	- `THINGSDB`：可选数据库覆盖路径；缺省时使用 `things.py` 自带的路径发现。
83	- `LOG_LEVEL`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT`。
84	- `WATCH_DEBOUNCE_SECONDS`。
85	- `FULL_SYNC_INTERVAL`。
86	- `AUTO_COMMIT`、`AUTO_PUSH`。
87	- `GIT_REMOTE`、`GIT_BRANCH`。
88	- Git 子进程超时。
89	
90	约束：`AUTO_PUSH=true` 时必须启用 `AUTO_COMMIT`。目标路径必须存在且为 Git 工作树。敏感配置不写入日志。
91	
92	### `src/models.py`
93	
94	定义项目内部不可变数据模型，将外部稀疏字典与渲染逻辑隔离。主要实体为：
95	
96	- `TaskSnapshot`
97	- `ChecklistItem`
98	- `ContainerSnapshot`
99	- `ThingsSnapshot`
100	
101	可选字段有明确的 `None` 或空集合默认值。状态只接受 `incomplete`、`completed`、`canceled`；类型只接受 MVP 用到的 `to-do`、`project`、`heading`。
102	
103	### `src/things_adapter.py`
104	
105	只使用 `things` 的读取接口：`tasks()`、`areas()`、`today()`、`upcoming()` 等，并把结果规范化为内部模型。
106	
107	该模块不导入或调用 `complete()`，也不构造 `update`/`update-project` URL。数据库访问失败后等待 10 秒重试，最多 3 次。只有读取并规范化完整快照成功后才向调用方返回结果。
108	
109	数据库定位遵循：
110	
111	1. 显式 `THINGSDB`。
112	2. `things.py` 对现代 `ThingsData-*` 路径的发现。
113	3. 参考库的旧路径回退。
114	
115	### `src/renderer.py`
116	
117	输入一个 `ThingsSnapshot`，输出 `dict[Path, str]`，键是相对于目标仓库的安全路径，值是确定性 UTF-8 Markdown 内容。
118	
119	职责包括：
120	
121	- 分配任务主位置和终态文件。
122	- 构造 Today/Upcoming 派生视图。
123	- 对任务进行稳定排序。
124	- 渲染任务区块、UUID 注释、元数据和 checklist。
125	- 清理文件名并解决路径冲突。
126	- 转义会破坏 Markdown 结构的单行内容。
127	
128	该模块不读取或写入文件，也不执行 Git。
129	
130	### `src/filesystem.py`
131	
132	协调期望文件集合与目标仓库当前状态：
133	
134	- 内容相同的文件不写入。
135	- 新内容先写入目标文件同目录下的临时文件，刷新后使用 `os.replace()` 原子替换。
136	- 删除不再存在的旧托管文件。
137	- 保留所有陌生文件。
138	- 返回新增、修改、删除的明确相对路径集合，供 Git 层使用。
139	
140	一次同步先完成快照读取和全部内容渲染，再开始修改目标仓库，避免数据库读取失败造成部分输出。
141	
142	### `src/git_ops.py`
143	
144	通过 `subprocess.run()` 封装 Git 命令，统一捕获 stdout、stderr 和超时。所有命令都设置工作目录和超时。
145	
146	行为规则：
147	
148	- 只执行 `git add -- <明确路径列表>`，不使用 `git add .`。
149	- 删除路径同样通过明确 pathspec 暂存。
150	- 仅当暂存区含同步器产生的差异时提交。
151	- 提交消息格式为：`Update: YYYY-MM-DD HH:MM | Added N, Modified N, Deleted N`。
152	- `AUTO_PUSH=true` 时执行 `git push <remote> <branch>`。
153	- 不自动 pull、merge 或 rebase。
154	- Git 失败时保留已落盘内容及本地提交，记录可操作的错误信息，等待下一次同步重试。
155	- 不暂存或修改仓库中其他未提交内容。
156	
157	### `src/sync_engine.py`
158	
159	协调一次同步，并使用互斥锁保证进程内最多只有一个同步执行：
160	
161	1. 获取完整 Things 快照。
162	2. 渲染期望文件。
163	3. 协调文件系统。
164	4. 无变化时结束。
165	5. 按配置提交和推送。
166	6. 记录耗时、文件数量和结果。
167	
168	启动同步、监听事件和定时校验均调用此入口。
169	
170	### `src/watcher.py`
171	
172	使用 `watchdog` 监听实际数据库文件所在目录，关注：
173	
174	- `main.sqlite`
175	- `main.sqlite-wal`
176	- `main.sqlite-shm`
177	
178	相关事件在配置的防抖窗口内合并为一次同步请求。事件处理线程不直接执行同步，而把请求交给串行协调逻辑。新事件若发生在同步期间，会在当前同步结束后至多补跑一次，避免丢失最终状态或形成无限并发。
179	
180	### `main.py`
181	
182	应用入口负责：
183	
184	1. 加载配置和初始化轮转日志。
185	2. 注册 `SIGINT`、`SIGTERM`。
186	3. 创建同步引擎并执行启动同步。
187	4. 启动文件监听与定时完整同步。
188	5. 退出时停止接收新请求，关闭监听和定时器，等待当前 Git 操作在既定超时内结束。
189	
190	## 输出结构
191	
192	```text
193	<REPO_PATH>/
194	├── Inbox.md
195	├── Today.md
196	├── Anytime.md
197	├── Someday.md
198	├── Upcoming.md
199	├── 已完成.md
200	├── 已取消.md
201	├── Projects/
202	│   └── <项目名>/
203	│       ├── tasks.md
204	│       ├── 已完成.md
205	│       └── 已取消.md
206	├── Areas/
207	│   └── <领域名>/
208	│       ├── tasks.md
209	│       ├── 已完成.md
210	│       └── 已取消.md
211	└── Archived/
212	    ├── Projects/
213	    └── Areas/
214	```
215	
216	空的固定顶层视图仍生成，以保持结构稳定。空 Project/Area 是否保留由当前快照中容器是否存在决定：存在的空容器保留目录和空的托管文件；消失或进入回收站的容器导出目录移入对应 `Archived` 子目录。
217	
218	由于 `things.py` 的 Area API 不提供可靠的回收站状态，Area 从快照消失只表示导出侧不再可见，不声称它在 Things 中具有特定“归档”状态。
219	
220	## 路径规则
221	
222	文件名清理遵循以下规则：
223	
224	- 将 `/`、`:`、`?`、`*`、`<`、`>`、`|`、`"` 和控制字符替换为 `-`。
225	- 去除首尾空白和结尾句点。
226	- 空名称使用实体类型加 UUID 短前缀。
227	- 限制单个路径段长度，为 `.md` 和冲突后缀预留空间。
228	- 两个名称清理后相同，或在默认不区分大小写的 macOS 文件系统上发生大小写冲突时，为所有冲突项追加稳定 UUID 短后缀。
229	
230	路径分配只依赖实体 UUID 和标题，同一快照的结果始终一致。
231	
232	## Markdown 合同
233	
234	每个文件第一行使用固定生成标识，随后是标题和任务区块。任务区块示例：
235	
236	```markdown
237	## [ ] 任务标题
238	<!-- uuid: ABC123DEF456 -->
239	- **创建时间**: 2025-01-15 10:30
240	- **修改时间**: 2025-01-15 14:20
241	- **开始日期**: 2025-01-16
242	- **截止日期**: 2025-01-20
243	- **提醒时间**: 09:00
244	- **项目**: 项目 A
245	- **领域**: 工作
246	- **标题分组**: 下一步
247	- **标签**: #工作 #重要
248	- **备注**:
249	  任务的详细描述内容
250	- **子任务**:
251	  - [ ] 子任务 1 <!-- uuid: SUB123 -->
252	  - [x] 子任务 2 <!-- uuid: SUB456 -->
253	
254	---
255	```
256	
257	规则：
258	
259	- `incomplete`、`completed`、`canceled` 分别映射为 `[ ]`、`[x]`、`[-]`。
260	- 缺失的可选字段整行省略，不输出空占位。
261	- 不输出参考库没有公开提供的优先级和 Evening 字段。
262	- 标题和单行字段转义换行及结构性 Markdown 字符。
263	- Notes 保留多行文本，统一换行符并缩进，使其保持在备注字段下。
264	- Checklist 项包含 UUID 和状态；可用时保留完成时间。
265	- UUID 是区块稳定身份，不从标题或路径推导。
266	- 文件和任务使用稳定排序，避免无业务变化的重新排列。
267	
268	## 容器移动与归档
269	
270	文件协调前，渲染器根据当前快照产生当前 Project/Area 路径映射。协调器还读取上一轮生成清单，以 UUID 识别容器重命名、消失和重新出现：
271	
272	- 重命名：将托管内容写入新路径，删除旧路径下的托管文件；陌生文件留在原目录并告警。
273	- 消失或进入回收站：将仅含托管文件的导出目录移到 `Archived/Projects` 或 `Archived/Areas`；若含陌生文件，不移动整个目录，只归档托管文件并保留陌生内容。
274	- 重新出现：从当前快照生成到活动路径；不会自动搬回用户添加的陌生文件。
275	
276	`Archived/` 是持久历史区，不属于“当前期望文件集合”的删除范围。已归档的托管文件会保留到用户显式清理；若同一容器 UUID 后续再次归档，则更新该 UUID 对应的归档位置，而不是创建无限重复副本。活动路径永远只反映当前快照。
277	
278	同步器维护一个带生成标识的清单文件，记录活动容器映射、归档容器 UUID、相对路径和托管文件集合。该清单属于同步器管理范围，并参与明确路径 Git 暂存。
279	
280	## 错误处理
281	
282	### 数据库读取
283	
284	- 最多尝试 3 次。
285	- 每次失败后等待 10 秒，再进行下一次尝试。
286	- 最终失败时，不进入文件协调和 Git 阶段。
287	- 记录异常类别和上下文，但不记录 token 或完整敏感路径配置。
288	
289	### 文件系统
290	
291	- 单文件写入使用同目录临时文件和原子替换。
292	- 临时文件失败时清理自身，不删除原文件。
293	- 某个文件协调失败会终止该轮 Git 操作，并记录已经成功落盘的路径；下一轮通过确定性快照收敛。
294	
295	### Git
296	
297	- 所有子进程有超时。
298	- 非零退出记录 stderr。
299	- 提交失败时不推送。
300	- 推送失败时保留本地提交。
301	- 远端领先或认证错误不触发自动冲突处理。
302	
303	## 配置与部署
304	
305	项目提供：
306	
307	- `.env.example`
308	- `requirements.txt`
309	- `setup.py` 交互式配置脚本
310	- `generate_launchd.py`
311	- `main.py`
312	- README 安装和运维说明
313	
314	依赖基线：
315	
316	- Python 3.9+
317	- `things.py>=1.0.1,<2`
318	- `watchdog>=2.1,<7`
319	- `python-dotenv>=0.19,<2`
320	
321	launchd 生成器在项目内生成 plist 预览。用户通过明确的 setup 步骤安装到 `~/Library/LaunchAgents`，普通同步进程不修改系统 launchd 配置。
322	
323	## 测试策略
324	
325	### 单元测试
326	
327	`tests/test_things_adapter.py`：
328	
329	- 使用内嵌参考库的 SQLite fixture 或等价测试数据库，通过 `THINGSDB` 注入。
330	- 验证稀疏字典规范化、状态映射、空字段、Project/Area/Heading 关系。
331	- 验证失败重试次数和间隔，不真实等待 10 秒。
332	- 验证适配器只调用读取 API。
333	
334	`tests/test_renderer.py`：
335	
336	- 顶层、Project、Area 主位置优先级。
337	- Today/Upcoming 派生重复展示。
338	- 完成和取消文件。
339	- Markdown 特殊字符、多行 Notes、Checklist 状态。
340	- 路径清理、空标题、重名和大小写冲突。
341	- 稳定排序和确定性输出。
342	
343	`tests/test_filesystem.py`：
344	
345	- 无变化不写入。
346	- 新增、原子修改、删除旧托管文件。
347	- 保留陌生文件。
348	- 容器重命名、归档及含陌生文件时的保守行为。
349	- 中途失败后下一轮收敛。
350	
351	`tests/test_git_ops.py`：
352	
353	- 明确 pathspec 暂存，不出现 `git add .`。
354	- 空差异不提交。
355	- 提交消息统计。
356	- 超时、非零退出和 stderr 日志。
357	- 提交失败禁止推送，推送开关生效。
358	
359	`tests/test_service.py`：
360	
361	- 防抖窗口合并事件。
362	- 同步期间事件触发至多一次补跑。
363	- 启动同步、定时同步复用同一入口。
364	- 优雅退出等待当前任务并停止新任务。
365	
366	### 集成测试
367	
368	在临时目录创建 Git 仓库，使用测试数据库完成：
369	
370	1. 快照生成 Markdown。
371	2. 修改 fixture 或输入快照后仅产生预期 diff。
372	3. 任务移动后旧位置消失、新位置出现。
373	4. 删除或隐藏容器后内容进入 `Archived`。
374	5. 自动提交只包含托管路径。
375	
376	真实 GitHub push、真实 Things 数据和 launchd 生命周期作为 README 中的人工验收步骤，不进入默认测试套件。
377	
378	## 验收标准
379	
380	MVP 完成时满足：
381	
382	1. 使用测试数据库启动后能生成完整目录结构和合法 Markdown。
383	2. 重复同步同一快照时，不修改文件且不创建提交。
384	3. 单个标题变化的 Git diff 仅包含相应任务标题行，除非排序或路径也确实发生变化。
385	4. 任务主位置遵循 Project → Area → 顶层列
… (truncated)
```

</details>

<details><summary>🔧 Read — /Users/oyamahappa/Documents/GitHub/Things3-push/docs/superpowers/plans/2026-09-04-things3-sync-mvp.md</summary>

Input:

```
{
  "file_path": "/Users/oyamahappa/Documents/GitHub/Things3-push/docs/superpowers/plans/2026-09-04-things3-sync-mvp.md"
}
```

Output:

```
1	# Things3 到 GitHub Markdown 同步 MVP Implementation Plan
2	
3	> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
4	
5	**Goal:** 构建一个 macOS 后台服务，只读监听 Things3 数据库，把完整任务快照确定性导出为 Markdown，并按配置自动提交和推送到 Git 仓库。
6	
7	**Architecture:** 所有触发源都调用同一条快照流水线：只读适配器规范化 Things 字典，纯渲染器生成期望文件和容器映射，文件协调器原子收敛磁盘状态，Git 层只暂存明确路径。服务层用防抖队列串行化数据库事件、启动同步和定时同步，并在信号退出时等待当前操作结束。
8	
9	**Tech Stack:** Python 3.9+、`things.py>=1.0.1,<2`、`watchdog>=2.1,<7`、`python-dotenv>=0.19,<2`、标准库 `dataclasses`/`pathlib`/`sqlite3`/`subprocess`/`threading`/`logging`、pytest。
10	
11	## Global Constraints
12	
13	- 运行平台为 macOS，Python 最低版本为 3.9。
14	- 运行时依赖必须限定为 `things.py>=1.0.1,<2`、`watchdog>=2.1,<7`、`python-dotenv>=0.19,<2`；测试依赖在 `requirements-dev.txt` 中声明。
15	- Things 数据库只能通过读取接口访问；业务代码不得导入或调用 `complete()`，不得构造 `update` 或 `update-project` URL。
16	- 所有文件路径使用 `pathlib.Path`；所有 Git 命令使用带超时的 `subprocess.run()`。
17	- 数据库读取失败后间隔 10 秒重试，最多 3 次；完整快照成功前不得修改目标仓库。
18	- 禁止使用 `git add .`；只暂存文件协调器返回的明确相对路径。
19	- 同步器只删除带生成标识的已知托管文件；陌生文件必须保留并记录警告。
20	- `AUTO_PUSH=true` 必须同时满足 `AUTO_COMMIT=true`。
21	- 不自动 pull、merge、rebase 或解决远端冲突。
22	- 输出中不包含参考库未公开的优先级、Evening、附件或重复规则字段。
23	- 现有 `.gitignore` 和 `docs/CHANGELOG.md` 是用户在本计划开始前已暂存的改动。每个实施提交必须使用 `git commit --only -- <本任务文件>`，不得修改或把它们带入功能提交。
24	- 本地 `things.py/` 已被忽略，只作为 API 源码和 SQLite 测试 fixture 参考，不作为主项目源码提交。
25	
26	## File Map
27	
28	### Runtime package
29	
30	- `src/__init__.py`：包版本。
31	- `src/models.py`：不可变快照模型、状态和容器类型。
32	- `src/config.py`：环境配置解析、校验及 Git 工作树检查。
33	- `src/utils.py`：日志初始化、布尔/数值配置解析和安全路径段处理。
34	- `src/things_adapter.py`：数据库路径发现、只读 API 协议、重试和字典规范化。
35	- `src/markdown.py`：单任务 Markdown 转义与渲染，不处理路由。
36	- `src/renderer.py`：任务路由、容器路径冲突消解、稳定排序和完整文件集合渲染。
37	- `src/filesystem.py`：manifest、原子写入、托管文件协调、容器重命名和归档。
38	- `src/git_ops.py`：明确 pathspec 暂存、差异检测、提交与推送。
39	- `src/sync_engine.py`：一次同步的事务边界和串行锁。
40	- `src/watcher.py`：SQLite/WAL/SHM 事件过滤、防抖和补跑调度。
41	- `src/service.py`：启动同步、周期同步和协调关闭。
42	- `main.py`：生产入口与信号处理。
43	- `setup.py`：交互式生成 `.env`。
44	- `generate_launchd.py`：在项目内生成 launchd plist 预览。
45	
46	### Configuration and documentation
47	
48	- `.env.example`：完整配置模板。
49	- `requirements.txt`：运行时依赖。
50	- `requirements-dev.txt`：pytest 与覆盖率依赖。
51	- `README.md`：安装、配置、运行、部署、输出和故障排查。
52	- `Agent.md`：按真实 API 和最终 MVP 行为修正文档并标记完成项。
53	
54	### Tests
55	
56	- `tests/conftest.py`：共享模型工厂和测试路径 fixture。
57	- `tests/test_config.py`：配置默认值和约束。
58	- `tests/test_models.py`：模型不变量。
59	- `tests/test_things_adapter.py`：API 规范化、数据库发现与重试。
60	- `tests/test_markdown.py`：Markdown 合同。
61	- `tests/test_renderer.py`：路径分配、主位置、派生视图和确定性。
62	- `tests/test_filesystem.py`：原子协调、manifest、删除保护和归档。
63	- `tests/test_git_ops.py`：Git 命令和失败分支。
64	- `tests/test_sync_engine.py`：流水线边界、无变化和 Git 策略。
65	- `tests/test_watcher.py`：事件过滤、防抖、同步期间补跑。
66	- `tests/test_service.py`：启动、周期和优雅退出。
67	- `tests/test_cli_tools.py`：`.env` 初始化和 plist 生成。
68	- `tests/test_integration.py`：测试数据库到临时 Git 仓库的端到端验收。
69	
70	---
71	
72	### Task 1: Project Foundation, Models, and Configuration
73	
74	**Files:**
75	- Create: `src/__init__.py`
76	- Create: `src/models.py`
77	- Create: `src/config.py`
78	- Create: `src/utils.py`
79	- Create: `.env.example`
80	- Create: `requirements.txt`
81	- Create: `requirements-dev.txt`
82	- Create: `tests/__init__.py`
83	- Create: `tests/test_models.py`
84	- Create: `tests/test_config.py`
85	
86	**Interfaces:**
87	- Consumes: no runtime interfaces from earlier tasks.
88	- Produces: `ChecklistItem`, `TaskSnapshot`, `ContainerSnapshot`, `ThingsSnapshot`, `ContainerPath`, `RenderedSnapshot`, `ChangeSet`, `SyncResult`; `AppConfig.from_env(env: Optional[Mapping[str, str]] = None, *, git_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> AppConfig`; `setup_logging(log_dir: Path, level: str, max_bytes: int, backup_count: int) -> None`; `sanitize_path_segment(title: str, fallback: str, max_length: int = 120) -> str`.
89	
90	- [ ] **Step 1: Declare runtime and test dependencies**
91	
92	Create `requirements.txt` exactly as:
93	
94	```text
95	things.py>=1.0.1,<2
96	watchdog>=2.1,<7
97	python-dotenv>=0.19,<2
98	```
99	
100	Create `requirements-dev.txt` exactly as:
101	
102	```text
103	-r requirements.txt
104	pytest>=8,<9
105	pytest-cov>=5,<7
106	```
107	
108	Create `.env.example` with non-user-specific values:
109	
110	```dotenv
111	REPO_PATH=/path/to/your/things-backup-repository
112	# THINGSDB=/path/to/Things Database.thingsdatabase/main.sqlite
113	LOG_LEVEL=INFO
114	LOG_MAX_BYTES=10485760
115	LOG_BACKUP_COUNT=5
116	WATCH_DEBOUNCE_SECONDS=2
117	FULL_SYNC_INTERVAL=3600
118	AUTO_COMMIT=true
119	AUTO_PUSH=true
120	GIT_REMOTE=origin
121	GIT_BRANCH=main
122	GIT_TIMEOUT_SECONDS=30
123	```
124	
125	- [ ] **Step 2: Write failing model tests**
126	
127	Create `tests/test_models.py`:
128	
129	```python
130	from dataclasses import FrozenInstanceError
131	from pathlib import Path
132	
133	import pytest
134	
135	from src.models import ChecklistItem, RenderedSnapshot, TaskSnapshot, ThingsSnapshot
136	
137	
138	def test_task_snapshot_is_immutable_and_normalizes_collections():
139	    task = TaskSnapshot(
140	        uuid="TASK-1",
141	        title="Ship release",
142	        status="incomplete",
143	        tags=("work",),
144	        checklist=(
145	            ChecklistItem(uuid="ITEM-1", title="Tag", status="completed"),
146	        ),
147	    )
148	
149	    assert task.tags == ("work",)
150	    assert task.checklist[0].status == "completed"
151	    with pytest.raises(FrozenInstanceError):
152	        task.title = "changed"
153	
154	
155	def test_task_snapshot_rejects_unknown_status():
156	    with pytest.raises(ValueError, match="Unsupported task status"):
157	        TaskSnapshot(uuid="TASK-1", title="x", status="blocked")
158	
159	
160	def test_rendered_snapshot_copies_files_into_a_read_only_mapping():
161	    source = {Path("Inbox.md"): "content"}
162	    rendered = RenderedSnapshot(source, ())
163	    source[Path("Today.md")] = "later mutation"
164	
165	    assert dict(rendered.files) == {Path("Inbox.md"): "content"}
166	    with pytest.raises(TypeError):
167	        rendered.files[Path("Inbox.md")] = "changed"
168	
169	
170	def test_snapshot_rejects_duplicate_task_uuids():
171	    one = TaskSnapshot(uuid="TASK-1", title="one", status="incomplete")
172	    duplicate = TaskSnapshot(uuid="TASK-1", title="two", status="completed")
173	
174	    with pytest.raises(ValueError, match="Duplicate task UUID"):
175	        ThingsSnapshot(tasks=(one, duplicate))
176	```
177	
178	- [ ] **Step 3: Run model tests and verify the import failure**
179	
180	Run:
181	
182	```bash
183	python3 -m pytest tests/test_models.py -v
184	```
185	
186	Expected: collection fails with `ModuleNotFoundError: No module named 'src'`.
187	
188	- [ ] **Step 4: Implement immutable domain models**
189	
190	Create `src/__init__.py`:
191	
192	```python
193	__version__ = "0.1.0"
194	```
195	
196	Create `src/models.py` with these exact public fields and validation rules:
197	
198	```python
199	from dataclasses import dataclass, field
200	from pathlib import Path
201	from types import MappingProxyType
202	from typing import Literal, Mapping, Optional, Tuple
203	
204	TaskStatus = Literal["incomplete", "completed", "canceled"]
205	ContainerKind = Literal["project", "area"]
206	ChangeKind = Literal["added", "modified", "deleted"]
207	
208	_VALID_STATUSES = {"incomplete", "completed", "canceled"}
209	
210	
211	@dataclass(frozen=True)
212	class ChecklistItem:
213	    uuid: str
214	    title: str
215	    status: TaskStatus
216	    stop_date: Optional[str] = None
217	    created: Optional[str] = None
218	    modified: Optional[str] = None
219	
220	    def __post_init__(self) -> None:
221	        if self.status not in _VALID_STATUSES:
222	            raise ValueError(f"Unsupported checklist status: {self.status}")
223	
224	
225	@dataclass(frozen=True)
226	class TaskSnapshot:
227	    uuid: str
228	    title: str
229	    status: TaskStatus
230	    task_type: str = "to-do"
231	    start: Optional[str] = None
232	    area_uuid: Optional[str] = None
233	    area_title: Optional[str] = None
234	    project_uuid: Optional[str] = None
235	    project_title: Optional[str] = None
236	    heading_uuid: Optional[str] = None
237	    heading_title: Optional[str] = None
238	    notes: Optional[str] = None
239	    tags: Tuple[str, ...] = field(default_factory=tuple)
240	    checklist: Tuple[ChecklistItem, ...] = field(default_factory=tuple)
241	    start_date: Optional[str] = None
242	    deadline: Optional[str] = None
243	    reminder_time: Optional[str] = None
244	    stop_date: Optional[str] = None
245	    created: Optional[str] = None
246	    modified: Optional[str] = None
247	    index: int = 0
248	    today_index: int = 0
249	    trashed: bool = False
250	
251	    def __post_init__(self) -> None:
252	        if self.status not in _VALID_STATUSES:
253	            raise ValueError(f"Unsupported task status: {self.status}")
254	        if self.task_type != "to-do":
255	            raise ValueError(f"Unsupported task type: {self.task_type}")
256	
257	
258	@dataclass(frozen=True)
259	class ContainerSnapshot:
260	    uuid: str
261	    kind: ContainerKind
262	    title: str
263	    area_uuid: Optional[str] = None
264	    area_title: Optional[str] = None
265	    index: int = 0
266	    trashed: bool = False
267	
268	
269	@dataclass(frozen=True)
270	class ThingsSnapshot:
271	    tasks: Tuple[TaskSnapshot, ...] = field(default_factory=tuple)
272	    projects: Tuple[ContainerSnapshot, ...] = field(default_factory=tuple)
273	    areas: Tuple[ContainerSnapshot, ...] = field(default_factory=tuple)
274	    today_uuids: Tuple[str, ...] = field(default_factory=tuple)
275	    upcoming_uuids: Tuple[str, ...] = field(default_factory=tuple)
276	
277	    def __post_init__(self) -> None:
278	        object.__setattr__(self, "tasks", tuple(self.tasks))
279	        object.__setattr__(self, "projects", tuple(self.projects))
280	        object.__setattr__(self, "areas", tuple(self.areas))
281	        object.__setattr__(self, "today_uuids", tuple(self.today_uuids))
282	        object.__setattr__(self, "upcoming_uuids", tuple(self.upcoming_uuids))
283	        task_ids = [task.uuid for task in self.tasks]
284	        container_ids = [container.uuid for container in self.projects + self.areas]
285	        if len(task_ids) != len(set(task_ids)):
286	            raise ValueError("Duplicate task UUID in snapshot")
287	        if len(container_ids) != len(set(container_ids)):
288	            raise ValueError("Duplicate container UUID in snapshot")
289	
290	
291	@dataclass(frozen=True)
292	class ContainerPath:
293	    uuid: str
294	    kind: ContainerKind
295	    relative_dir: Path
296	
297	
298	@dataclass(frozen=True)
299	class RenderedSnapshot:
300	    files: Mapping[Path, str]
301	    containers: Tuple[ContainerPath, ...]
302	
303	    def __post_init__(self) -> None:
304	        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))
305	        object.__setattr__(self, "containers", tuple(self.containers))
306	
307	
308	@dataclass(frozen=True)
309	class ChangeSet:
310	    added: Tuple[Path, ...] = field(default_factory=tuple)
311	    modified: Tuple[Path, ...] = field(default_factory=tuple)
312	    deleted: Tuple[Path, ...] = field(default_factory=tuple)
313	    git_paths: Tuple[Path, ...] = field(default_factory=tuple)
314	
315	    @property
316	    def paths(self) -> Tuple[Path, ...]:
317	        return tuple(sorted(set(self.added + self.modified + self.deleted)))
318	
319	    @property
320	    def changed(self) -> bool:
321	        return bool(self.paths)
322	
323	    def __post_init__(self) -> None:
324	        object.__setattr__(self, "added", tuple(sorted(set(self.added))))
325	        object.__setattr__(self, "modified", tuple(sorted(set(self.modified))))
326	        object.__setattr__(self, "deleted", tuple(sorted(set(self.deleted))))
327	        if self.git_paths:
328	            object.__setattr__(self, "git_paths", tuple(sorted(set(self.git_paths))))
329	        elif self.paths:
330	            object.__setattr__(self, "git_paths", self.paths)
331	
332	
333	@dataclass(frozen=True)
334	class SyncResult:
335	    changes: ChangeSet
336	    committed: bool = False
337	    pushed: bool = False
338	```
339	
340	Every snapshot `__post_init__` must normalize externally supplied lists to tuples. `RenderedSnapshot` must copy `files` and wrap that copy in `MappingProxyType`; a frozen dataclass alone does not prevent a caller from mutating a supplied dict. `ThingsSnapshot` rejects duplicate container UUIDs across projects and areas as well as duplicate task UUIDs. `ChangeSet.__post_init__` must normalize all explicit path sequences to sorted unique tuples and derive `git_paths` from `paths` only when no historical pathspec was supplied.
341	
342	- [ ] **Step 5: Run model tests and verify they pass**
343	
344	Run:
345	
346	```bash
347	python3 -m pytest tests/test_models.py -v
348	```
349	
350	Expected: 4 tests pass.
351	
352	- [ ] **Step 6: Write failing configuration and utility tests**
353	
354	Create `tests/test_config.py`:
355	
356	```python
357	from pathlib import Path
358	from typing import Dict
359	from unittest.mock import Mock
360	
361	import pytest
362	
363	from src.config import AppConfig
364	from src.utils import sanitize_path_segment
365	
366	
367	def valid_env(repo: Path) -> Dict[str, str]:
368	    return {
369	        "REPO_PATH": str(repo),
370	        "AUTO_COMMIT": "true",
371	        "AUTO_PUSH": "false",
372	    }
373	
374	
375	def test_config_applies_documented_defaults(tmp_path):
376	    repo = tmp_path / "repo"
377	    repo.mkdir()
378	
379	    def runner(command, **kwargs):
380	        stdout = "true\n" if command[1] == "rev-parse" else "main\n"
381	        return Mock(returncode=0, stdout=stdout, stderr="")
382	
383	    runner = Mock(side_effect=runner)
384	    config = AppConfig.from_env(valid_env(repo), git_runner=runner)
385	
386	    assert config.repo_path == repo.resolve()
387	    assert config.watch_debounce_seconds == 2.0
388	    assert config.full_sync_interval == 3600.0
389	    assert config.git_timeout_seconds == 30.0
390	    assert config.git_remote == "origin"
391	    assert config.git_branch == "main"
392	    assert runner.call_count == 2
393	
394	
395	def test_config_rejects_push_without_commit(tmp_path):
396	    repo = tmp_path / "repo"
397	    repo.mkd
… (truncated)
```

</details>

<details><summary>🔧 Read — /Users/oyamahappa/Documents/GitHub/Things3-push/.superpowers/sdd/2026-09-04-things3-sync-mvp/progress.md</summary>

Input:

```
{
  "file_path": "/Users/oyamahappa/Documents/GitHub/Things3-push/.superpowers/sdd/2026-09-04-things3-sync-mvp/progress.md"
}
```

Output:

```
1	# SDD ledger — plan: docs/superpowers/plans/2026-09-04-things3-sync-mvp.md
2	
3	Task 3: complete (commits 487fab0..0d2a875, review clean; independent spec and quality Approved; current Markdown tests: 4 passed; evidence task-3-review.md)
4	
5	Task 1: complete (commits 45df0d6..abb26d5, review clean)
6	Task 2: complete (commits abb26d5..487fab0, review clean; `/tmp/things3-sync-mvp-test-venv/bin/python -m pytest tests/test_things_adapter.py -v` with `PYTHONPATH=things.py:.`: 7 passed)
7	Task 4: fix round 1/5 (case-only UUID path collision addressed; current Task 4 files uncommitted)
8	Task 4: fix round 2/5 (hostile UUID path content addressed; current Task 4 files uncommitted)
9	Task 4: parked — title backslashes are Windows separators — ruling: user selected macOS/POSIX-only path semantics; `sanitize_path_segment` intentionally follows the documented macOS invalid-character list, so backslash remains a title character.
10	Task 4: complete (uncommitted worktree changes from d4a17d7, review clean under macOS/POSIX path semantics; 32 passed; two Important findings fixed; one cross-platform finding parked by user ruling)
11	Task 5: fix round 1/5 (ancestor ownership preflight, exact manifest schema, and non-UTF-8 destination handling addressed)
12	Task 5: fix round 2/5 (direct/ancestor symlinks and invalid UTF-8 manifests addressed)
13	Task 5: fix round 3/5 (manifest destination symlink preflight addressed)
14	Task 5: complete (uncommitted files from d4a17d7; review clean; spec and quality PASS; 23 focused filesystem tests and 55 project tests passed; evidence task-5-rereview-round-3.md)
15	Task 6: minor (deferred): _remove_empty_container_directories can log a misleading warning for an unchanged/nonempty active container; review task-6-review.md
16	Task 6: minor (deferred): active_previous_paths is computed but unused; review task-6-review.md
17	Task 6: complete (uncommitted filesystem changes; review clean; spec PASS and quality PASS with deferred minors; 32 focused filesystem tests and 64 project tests passed; evidence task-6-review.md)
18	
```

</details>

### 🤖 Assistant · 2026-09-06 21:04:33

Failed to authenticate. API Error: 401 无效的令牌 (request id: 202609061304322843588368268d9d6h5cX0RTy)

### 🤖 Assistant · 2026-09-06 21:33:27

No response requested.

### 👤 User · 2026-09-06 21:33:27

继续

### 🤖 Assistant · 2026-09-06 21:33:34

Failed to authenticate. API Error: 401 无效的令牌 (request id: 202609061333333436914518268d9d6VYmxdnys)

### 🤖 Assistant · 2026-09-06 22:02:05

No response requested.

### 👤 User · 2026-09-06 22:02:05

继续

### 🤖 Assistant · 2026-09-06 22:02:13

Failed to authenticate. API Error: 401 无效的令牌 (request id: 202609061402117039657508268d9d6pCitHeBG)

