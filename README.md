# codex-thread-skills

**可由 Codex / ChatGPT Work 使用的桌面会话清理技能 / Desktop thread cleanup for Codex and ChatGPT Work**

清理无法归档、源文件损坏或删除后仍出现在侧边栏的本地会话。提供 `codex-session-cleanup` 技能和一个仅依赖 Python 标准库的清理脚本，覆盖 Windows 与 macOS 的操作方式。

Clean up local conversations that cannot be archived, have damaged source files, or remain in the sidebar after deletion. Includes the `codex-session-cleanup` skill, a Python standard-library script, and Windows/macOS workflows.

本文逐项提供中英文对照：问题、链接获取截图、安装、使用步骤、技巧和注意事项。
This guide pairs Chinese and English explanations for the problem, screenshot walkthrough, installation, usage, tips and cautions.

## Codex 与 ChatGPT Work 都能套用 / Using it from Codex or ChatGPT Work

技能按实际能力选择流程，而不是限定执行助手。两者都能理解同一套说明；本机数据的删除仍须能访问对应电脑，或由用户在本机执行脚本。
The skill routes by available capabilities rather than assistant identity. Both can follow the same instructions; deleting computer-local data requires access to that computer or user execution of the local script.

| 使用环境 / Environment | 怎么使用 / How to use |
| --- | --- |
| Codex 或 Work 有本机终端、文件权限 / Codex or Work with local shell and file access | 加载技能，提供链接，预览后执行已授权的清理。Load the skill, supply links, preview and perform authorized cleanup. |
| ChatGPT Work 仅能在云端处理 / ChatGPT Work with cloud-only execution | 将 `SKILL.md`、脚本和存储说明作为任务附件，要求按本机平台生成命令；你在本机执行，再把 JSON 结果交给 Work 核验。Attach the skill, script and storage guide; ask for platform-specific commands, run them locally and return the JSON for interpretation. |
| 客户端提供原生任务删除接口 / Client provides a native task-deletion interface | 优先用对应接口处理支持的任务；保留精确 ID 和核验步骤。Prefer that interface for supported tasks, retaining exact IDs and verification. |
| 目标是普通 ChatGPT 云端聊天 / Target is an ordinary ChatGPT cloud chat | 使用产品提供的删除功能；本脚本只认识 Codex 本地存储，不能直接套用到云端聊天库。Use the product's deletion feature; this script understands Codex local stores, not ordinary cloud chat databases. |

应用名称、链接和数据格式是不同层次。即使界面名称变化，技能也会先核验存储结构；无法访问本机时会交付可运行命令并说明尚未执行。
App name, link format and storage schema are separate concerns. Even if the UI name changes, the skill verifies the schema first. Without local access it provides runnable commands and states that execution is pending.

## 解决什么问题？ / What problem does this solve?

| 遇到的问题 / Problem | 技能的处理 / What the skill does |
| --- | --- |
| 点击归档失败，提示找不到可读会话。Archiving fails because no readable thread can be found. | 按完整 UUID 找到本地源文件与数据库记录，即使源文件损坏也能定位。Locates rollouts and database rows by exact UUID, including damaged rollouts. |
| `.jsonl` 会话文件损坏，例如内容全为空字节。A `.jsonl` rollout is damaged, for example filled with null bytes. | 删除用户明确指定的损坏文件及相关记录；是否损坏需实际检查，不能仅凭归档失败推断。Removes the explicitly selected file and related records. Damage must be inspected, not inferred from archive failure alone. |
| 源文件已删，重启后侧边栏仍显示，还要再手动归档。A deleted thread survives in the sidebar after restart and requires another manual archive. | 同步清理桌面应用独立的 `local_thread_catalog`，更新目录修订号。Also clears the independent desktop catalog and updates its revision. |
| 有多个失效会话，要逐个重复处理。Several stale conversations need the same cleanup. | 支持多个深度链接或 UUID 一次批量处理、重复执行及结果核验。Accepts multiple deep links or UUIDs, supports repeat runs and verification. |

**预期结果：**指定会话的已知本地存储记录与侧边栏目录条目清空，重启后刷新界面，通常无需二次归档。脚本能验证磁盘数据，不能代替实际重启后的界面检查。

**Expected result:** the selected threads disappear from known local stores and the desktop catalog. Restarting refreshes the UI, normally without another archive click. Disk verification does not substitute for checking the UI after restart.

只想隐藏会话时使用 Codex 的普通归档功能。本技能的 `--apply` 会删除记录。
Use ordinary Codex archiving when you only want to hide a conversation. This skill's `--apply` deletes records.

## 第一步：复制会话深度链接 / Step 1: Copy the thread deep link

![右键会话，复制，复制深度链接 / Right-click the thread, Copy, Copy deep link](docs/images/copy-thread-deep-link.png)

| 步骤 | 中文 | English |
| --- | --- | --- |
| 1 | 在左侧列表找到有问题的会话。 | Find the problematic conversation in the sidebar. |
| 2 | 右键点击该会话；macOS 可双指点击或按住 Control 点击。 | Right-click that conversation; on macOS use a two-finger click or Control-click. |
| 3 | 展开「复制」选项。 | Open the **Copy** submenu. |
| 4 | 点击「复制深度链接」。 | Click **Copy deep link**. |
| 5 | 将链接粘贴到另一个正常会话，交给技能处理。多个链接可每行一个。 | Paste the link into another working conversation for the skill. Put multiple links on separate lines. |

链接格式示例 / Example link format:

```text
codex://threads/01a05091-d9cd-7612-b6c2-033360192471
```

这是文档示例，不是自动清理目标。执行命令时必须替换成你自己确认要删除的会话。
This is a documentation example, not an automatic target. Replace examples with conversations you intend to delete before running commands.

## 安装 / Installation

环境要求：Python 3.10 或更新版本；使用本机 Codex 数据目录。脚本无第三方运行时依赖。Git 用于克隆仓库。提供 Windows PowerShell 和 macOS Terminal（zsh/Bash）命令；仓库 CI 在两种系统上验证合成数据行为，真实客户端仍需确认存储布局。

Requirements: Python 3.10+, access to the local Codex data home, and Git for cloning. No third-party runtime dependencies. Commands cover Windows PowerShell and macOS Terminal (zsh/Bash); repository CI checks synthetic-data behavior on both systems. Confirm the real client's storage layout before use.

可直接告诉 Codex / You can ask Codex:

```text
请从 https://github.com/turtoncarllyle/codex-thread-skills/tree/main/codex-session-cleanup 安装这个技能。
Install the skill from https://github.com/turtoncarllyle/codex-thread-skills/tree/main/codex-session-cleanup.
```

手动安装 / Manual installation (PowerShell):

```powershell
git clone https://github.com/turtoncarllyle/codex-thread-skills.git
if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
$skillDataHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$skillTarget = Join-Path $skillDataHome 'skills\codex-session-cleanup'
New-Item -ItemType Directory -Force -Path $skillTarget | Out-Null
Copy-Item -Path '.\codex-thread-skills\codex-session-cleanup\*' -Destination $skillTarget -Recurse -Force
```

从仓库父目录执行。已克隆则跳过克隆行；复制命令可重复执行，覆盖同名技能文件。安装后重启 Codex 或新建任务，让它重新发现技能。
Run from the parent of the repository. Skip cloning if it already exists; repeating the copy updates files in place. Restart Codex or open a new task so the skill can be discovered.

macOS Terminal（zsh/Bash）安装 / macOS Terminal installation:

```bash
git clone https://github.com/turtoncarllyle/codex-thread-skills.git
# 克隆失败时先解决问题再继续 / Resolve a clone failure before continuing.
skill_data_home="${CODEX_HOME:-$HOME/.codex}"
skill_target="$skill_data_home/skills/codex-session-cleanup"
mkdir -p "$skill_target"
cp -R ./codex-thread-skills/codex-session-cleanup/. "$skill_target/"
```

在没有本机技能目录的 ChatGPT Work 环境中，无需执行安装命令。将仓库中的 [SKILL.md](codex-session-cleanup/SKILL.md)、[清理脚本](codex-session-cleanup/scripts/cleanup_threads.py) 和[存储说明](codex-session-cleanup/references/storage-map.md) 提供给任务，并要求遵循技能流程。若当前环境支持技能安装，使用它提供的安装入口。
In ChatGPT Work without a local skill directory, skip the installation commands. Provide [SKILL.md](codex-session-cleanup/SKILL.md), the [script](codex-session-cleanup/scripts/cleanup_threads.py) and [storage guide](codex-session-cleanup/references/storage-map.md) to the task and ask it to follow the workflow. If the environment has a skill installer, use that supported entry point.

## 最简单的用法 / The easiest way to use it

在另一个正常任务中调用技能，附上刚复制的链接。
Invoke the skill in another working task and paste the link you copied.

仅检查，不删除 / Diagnose only:

```text
使用 $codex-session-cleanup 检查下面的会话为什么无法归档，只预览，不删除：
<粘贴你的会话深度链接>

Use $codex-session-cleanup to diagnose why this thread cannot be archived. Preview only:
<paste your thread deep link>
```

确认需要删除 / Request deletion:

```text
使用 $codex-session-cleanup 从本地源头删除以下会话，同步清理侧边栏目录和索引，核验结果：
<粘贴一个或多个会话深度链接，每行一个>

Use $codex-session-cleanup to delete these local threads, including their sidebar catalog
and index entries, and verify the result:
<paste one or more thread deep links, one per line>
```

技能会定位数据目录、预览范围、执行已授权的删除并核验。目标仍在运行时先停止该任务；清理后重启刷新。仅请求诊断时不会自动删除。
The skill resolves the data home, previews scope, performs the authorized deletion and verifies it. Stop a target task if it is still running, then restart after cleanup to refresh. A diagnostic request does not trigger deletion.

ChatGPT Work 无本机权限时可用的提示词 / Prompt for Work without local access:

```text
请按照附件 codex-session-cleanup 技能处理这些会话。我使用 macOS（或 Windows）。
先说明本机执行步骤并生成准确命令；等我返回执行结果后，再帮我核验是否清理完成。
<粘贴深度链接>

Follow the attached codex-session-cleanup skill for these threads. I use macOS (or Windows).
Provide exact local commands first, then verify completion from the output I return.
<paste deep links>
```

## 手动操作步骤 / Manual CLI steps

以下命令从仓库根目录运行，示例 UUID 为虚构值。把 `$threadLinks` 替换成实际目标，把 `$cleanupHome` 改为自己的数据目录。自定义安装可用 `E:\codex\.codex`，默认值通常为用户目录下 `.codex`。

Run these commands from the repository root. UUIDs below are synthetic. Replace `$threadLinks` with your targets and `$cleanupHome` with your data home. Custom installations may use `E:\codex\.codex`; the default is usually `.codex` under your user directory.

```powershell
$cleanupScript = '.\codex-session-cleanup\scripts\cleanup_threads.py'
$cleanupHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$threadLinks = @(
    'codex://threads/11111111-1111-4111-8111-111111111111',
    'codex://threads/22222222-2222-4222-8222-222222222222'
)
```

### 1. 预览 / Preview

```powershell
python $cleanupScript --home $cleanupHome @threadLinks
```

默认只读，输出删除文件、改写索引、数据库行数及 `blockers`。核对精确 ID，先处理 blockers；没有匹配项时不需要删除。
Read-only by default. Lists files, index rewrites, row counts and blockers. Check exact IDs and resolve blockers first. No matches means no deletion is needed.

### 2. 执行 / Apply

推荐稳定方式：先关闭所有使用该数据目录的 Codex 客户端，再在独立 PowerShell 窗口中运行：
For stable results, close all Codex clients using this data home, then run in a separate PowerShell window:

Windows 请确认托盘或后台客户端也退出；macOS 用 `⌘Q` 退出应用，关闭窗口不一定结束进程。
On Windows also exit tray/background clients; on macOS use `⌘Q`, because closing a window may leave the app running.

```powershell
python $cleanupScript --home $cleanupHome --apply --offline @threadLinks
```

如果在 Codex 内执行，目标任务必须已停止，并传入当前执行任务 ID（不是待删目标）。用真实 ID 替换以下占位符：
If running inside Codex, targets must be stopped. Supply the current executing task ID, not a target ID. Replace this placeholder with its real ID:

```powershell
python $cleanupScript --home $cleanupHome --apply --protect-thread '<current-task-UUID>' @threadLinks
```

脚本也会读取 `CODEX_THREAD_ID` 进行保护。当前会话不能删除自己；改在另一个会话或外部终端执行。
The script also protects `CODEX_THREAD_ID` when available. A task cannot delete itself; use another task or an external terminal.

### 3. 核验 / Verify

```powershell
python $cleanupScript --home $cleanupHome --verify @threadLinks
$LASTEXITCODE
```

| 输出 / Output | 含义 / Meaning |
| --- | --- |
| `remaining_entries: 0` 且 `blockers: []` | 已知本地存储中无待处理项。No remaining work in known local stores. |
| `desktop_catalog_found: true` | 找到了可识别的桌面目录；为 false 时不能证明侧边栏已清理。A recognized desktop catalog was found; false means sidebar cleanup is unverified. |
| `databases_checked` | 展示实际检查的数据库路径，便于确认客户端的数据位置。Lists actual database paths inspected so you can confirm the client's data location. |
| 退出码 / exit code `0` | 预览无阻塞，或执行/核验成功。Preview has no blockers, or apply/verify succeeded. |
| 退出码 / exit code `1` | 输入、路径、数据库或执行错误；可能已部分完成。Input/path/database/execution error; partial cleanup is possible. |
| 退出码 / exit code `2` | 发现阻塞，或执行/核验后仍有残留。Blockers found, or residual entries remain after apply/verify. |

### 4. 重启刷新 / Restart and refresh

重新启动 Codex 查看侧边栏。脚本同时清理桌面目录，通常无需再手动点击归档。若仍显示，先重新 `--verify` 判断磁盘残留还是界面状态，再参阅[存储与排障](codex-session-cleanup/references/storage-map.md)。
Reopen Codex and inspect the sidebar. Clearing the desktop catalog normally removes the need for another archive click. If an entry remains, run `--verify` again to distinguish disk residuals from UI state, then consult the [storage guide](codex-session-cleanup/references/storage-map.md).

## macOS 完整命令 / Complete macOS commands

在仓库根目录的 Terminal 中执行。先替换虚构 ID，预览后确认范围；执行删除前用 `⌘Q` 退出使用该目录的所有客户端。
Run in Terminal at the repository root. Replace the synthetic UUID first, inspect the preview, then quit all clients using that home with `⌘Q` before applying.

```bash
cleanup_script='./codex-session-cleanup/scripts/cleanup_threads.py'
cleanup_home="${CODEX_HOME:-$HOME/.codex}"
thread_links=(
  'codex://threads/11111111-1111-4111-8111-111111111111'
  'codex://threads/22222222-2222-4222-8222-222222222222'
)

# 预览 / Preview
python3 "$cleanup_script" --home "$cleanup_home" "${thread_links[@]}"

# 退出客户端后执行 / Apply after quitting clients
python3 "$cleanup_script" --home "$cleanup_home" --apply --offline "${thread_links[@]}"

# 核验 / Verify
python3 "$cleanup_script" --home "$cleanup_home" --verify "${thread_links[@]}"
echo $?
```

不要一口气粘贴执行全部步骤；先看每一步结果。若在支持本机工具的助手中执行，使用 `--protect-thread` 路径，并让助手识别当前任务 ID。
Run steps individually and inspect each result. When an assistant with local tools executes the commands, use the protected-task route and have it identify its current task ID.

| 平台 / Platform | 默认数据目录 / Default home | 终端 / Shell | 完全退出 / Full exit |
| --- | --- | --- | --- |
| Windows | `%USERPROFILE%\.codex` | PowerShell, `python` | 退出应用及托盘实例 / Exit app and tray instances |
| macOS | `~/.codex` | zsh/Bash, `python3` | `⌘Q` |

两端都优先使用 `CODEX_HOME`，再由显式 `--home` 覆盖。若实际桌面目录数据库在别处，先确认其表结构，再用 `--catalog-db '准确路径'`。不要对 AppData 或 `~/Library/Application Support` 整个目录进行清空。
Both honor `CODEX_HOME`, overridden by explicit `--home`. If the actual desktop catalog lives elsewhere, verify its schema and use `--catalog-db 'exact path'`. Never clear all of AppData or `~/Library/Application Support`.

## 参数与使用技巧 / Options and tips

| 参数或技巧 / Option or tip | 说明 / Explanation |
| --- | --- |
| `--home PATH` | 明确选择数据目录，优先于 `CODEX_HOME` 和默认目录。Explicit data home; overrides environment and default. |
| `--catalog-db PATH` | 客户端目录数据库在其他位置时显式指定；先验证目录表结构。Explicit catalog database for alternate client layouts; schema is checked first. |
| 不加模式参数 / No mode flag | 默认预览；第一次使用先看计划。Preview by default; inspect it on the first run. |
| `--apply` | 执行删除并重新扫描核验。Delete and rescan for verification. |
| `--verify` | 单独只读核验，不做修复。Read-only verification without repair. |
| `--protect-thread UUID` | 保护当前或其他重要会话，可重复传入。Protect the current or other important tasks; repeatable. |
| `--offline` | 声明客户端已关闭；不负责关闭或检测进程。Assert clients are closed; does not close or detect processes. |
| 批量 / Batch | 每个链接作为一个参数；自动去重。One argument per link; duplicates are deduplicated. |
| 可重复执行 / Repeatable | 失败后先排查原因，再对相同 ID 重试；已删除项不会扩展到其他会话。Resolve failures before retrying the same IDs; already removed items do not expand the scope. |
| Windows junction | 自动解析真实目录，避免 `C:` 与 `E:` 两个入口重复处理同一数据。Resolve the real home so two junction paths do not double-process the same data. |
| WindowsApps 下 `rg` 被拒 / `rg` blocked in WindowsApps | 排查时使用 `Get-ChildItem`、`Select-String`；脚本本身不依赖 `rg`。Use native PowerShell for inspection; the script does not depend on `rg`. |

## 注意事项 / Cautions

| 中文 | English |
| --- | --- |
| `--apply` 是删除，不是归档；默认不生成对话备份。需要备份时先自行保存并明确保存位置。 | Apply deletes rather than archives and does not create conversation backups. Save any wanted copy first in a location you choose. |
| 只删精确指定 ID，不按标题模糊匹配，不递归删除子任务，不删除项目源码和 worktree。 | Only exact selected IDs are deleted; no fuzzy-title matching, recursive child deletion, project-source or worktree deletion. |
| 不处理云端或远程主机记录；匹配到非本机目录记录会停止。 | Cloud and remote-host deletion are out of scope; non-local catalog matches stop the operation. |
| 应用运行时可能写回缓存。哈希检查只能减少竞态，稳定方式是关闭客户端后从外部终端执行。 | A live app can rewrite cached state. Hash checks reduce races; the stable method uses an external terminal after clients close. |
| 多个数据库与文件之间没有整体原子事务，失败可能部分完成；再次预览和核验后可精确重试。 | There is no global atomic transaction across stores; failure can leave partial completion. Preview and verify before an exact-ID retry. |
| 历史备份、日志、附件、云端副本及 SQLite 空闲页/WAL 中的旧内容不属于擦除范围；即时 `.codex-global-state.json.bak` 会同步清理。 | Historical backups, logs, attachments, cloud copies and old SQLite page/WAL contents are outside the erasure scope; the immediate global-state `.bak` mirror is cleaned. |
| 属于内部格式维护，不是官方删除 API。新表结构、触发器、未知依赖或关联自动化会阻止执行，须先审查处理。 | This maintains internal formats, not an official deletion API. New schemas, triggers, unknown dependencies or linked automations block execution pending review. |
| 本技能不验证“无法恢复”，也不承诺重启后的 UI 状态已经验收。 | This skill does not verify forensic irrecoverability or claim unobserved post-restart UI validation. |

## 仓库结构与验证 / Repository and validation

```text
codex-thread-skills\
├── README.md                         中英文对照说明 / Bilingual guide
├── LICENSE                           MIT
├── docs\images\copy-thread-deep-link.png
├── tests\test_cleanup.py             隔离行为测试 / Isolated behavior tests
└── codex-session-cleanup\
    ├── SKILL.md                      技能入口 / Skill instructions
    ├── agents\openai.yaml            技能显示信息 / UI metadata
    ├── scripts\cleanup_threads.py    清理脚本 / Cleanup script
    └── references\storage-map.md      存储排障说明 / Storage troubleshooting
```

开发验证 / Development validation:

```powershell
python -m unittest discover -s tests -v
```

测试创建隔离的 SQLite/JSON/rollout 数据，覆盖精确删除、侧边栏修订号、重复执行、当前任务保护、路径边界与并发变更等。测试不删除用户实际会话。
Tests create isolated SQLite/JSON/rollout fixtures for exact deletion, catalog revisions, idempotence, current-task protection, path boundaries and concurrent changes. Tests do not delete real user conversations. On macOS use `python3 -m unittest discover -s tests -v`.

[MIT License](LICENSE)
