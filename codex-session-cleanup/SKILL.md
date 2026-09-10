---
name: codex-session-cleanup
description: Resolve conversations that cannot be archived and remain stuck in the task list or sidebar (会话无法归档、一直存在、重启后仍显示). Reusable by Codex or ChatGPT Work on Windows/macOS to inspect exact thread links and remove authorized local remnants, including corrupt rollouts and stale desktop catalog entries. Route by actual local or cloud capabilities.
---

# Codex 会话清理 / Codex session cleanup

核心用途：处理会话无法归档、长期存在于列表、重启后仍在侧边栏中的问题。接受用户复制的会话深度链接，定位并清理源文件和各层残留记录。
Primary purpose: resolve unarchivable conversations that persist in the list or sidebar after restart. Accept copied thread deep links, locate their source files and clean up records across the relevant stores.

将用户明确指定的本地会话从源文件、数据库、索引及桌面目录中删除。
Remove explicitly selected local threads from rollouts, databases, indexes, and the desktop catalog.

## 能力路由 / Capability routing

本技能可由 Codex 或 ChatGPT Work 执行。先区分执行助手、桌面客户端和目标存储，不根据应用显示名或助手名称推断数据库布局。
Codex or ChatGPT Work can follow this skill. Distinguish the executing assistant, desktop client and target storage; neither product names nor assistant identity establish a database layout.

| 可用能力 / Available capability | 执行方式 / Route |
| --- | --- |
| 本机文件与命令权限 / Local filesystem and shell | 确认目标是受支持的 Codex 本地存储后，执行下方脚本流程。Verify the supported Codex local schema, then use the script workflow below. |
| 受支持的应用连接器 / Supported app connector | 对相应主机使用原生归档或删除接口，按接口真实语义报告；不要将归档说成删除。Use the appropriate native archive/delete interface for the correct host; report its actual semantics. |
| 只有云端执行、无法访问本机 / Cloud-only execution without local access | 完成链接解析和范围说明，提供脚本与对应平台命令，交给用户在本机外部终端执行；根据用户返回的 JSON 核验。明确等待本机执行，不能声称已删。Parse links and scope, provide the script and platform commands for local execution, then interpret returned JSON. State that local execution is pending; do not claim completion. |
| 普通 ChatGPT 云端聊天或未知存储 / Ordinary ChatGPT cloud chat or unknown schema | 使用该产品可用的受支持接口；没有接口则提供实际 UI 操作说明。不要把聊天 ID 转换成 rollout 文件并修改猜测的数据库。Use supported product interfaces, or UI instructions if unavailable. Never turn a chat ID into a guessed rollout/database mutation. |

缺少本机能力时，脚本与 reference 可以作为文件交给用户；不要尝试从云端访问用户电脑路径。
When local capabilities are absent, supply the script and reference as files; do not attempt to access user-computer paths from a cloud runtime.

## 选择操作 / Choose the operation

- 仅要求归档时使用应用归档工具；不要把归档当作永久删除。用户要求源头删除、无法归档后的清理，或延续本次批量删除时，使用此流程。先说明将删除的精确 ID 和范围。用户已经明确授权这些 ID 的删除时，预览无异常即可执行，无需重复询问。
  For ordinary archiving use the app tool; distinguish it from deletion. Use this workflow for explicit local deletion, cleanup after failed archiving, or continuation of an authorized batch. State exact IDs and scope. Existing explicit authorization for those IDs is sufficient after a clean preview.
- 诊断不等于删除授权。无法推断目标 ID 时，先定位并请用户明确；不要按标题模糊匹配或扩大到同项目其他会话。
  Diagnosis alone is not deletion authorization. Resolve missing identities before mutation; never delete by fuzzy title or include other project threads.
- 仅处理所选本机数据目录。远程主机、云端任务使用相应接口；不要把本地目录清理描述成云端删除或安全擦除。
  Operate on the selected local data home only. Remote/cloud tasks require their own interfaces; local cleanup is not cloud deletion or secure erasure.

## 执行 / Execute

1. 从链接提取完整 UUID，去重并保护当前任务。用环境 `CODEX_THREAD_ID` 或调用上下文确认当前 ID，不要猜测。当前任务也在删除列表时，改用另一任务或关闭应用后的独立终端。
   Extract full UUIDs, deduplicate, and protect the current task using `CODEX_THREAD_ID` or verified invocation context. If the current task is a target, use another task or an external terminal with the app closed.
2. 确认数据目录：显式 `--home`，其次 `CODEX_HOME`，最后用户目录的 `.codex`。解析 Windows junction 后只处理一份实际目录。Windows 使用反斜杠及 UTF-8；WindowsApps 禁止启动 `rg` 时使用 PowerShell 原生命令。
   Resolve the data home from explicit `--home`, then `CODEX_HOME`, then the user's `.codex`. Resolve junctions to avoid duplicate edits. Use UTF-8, Windows backslashes, and native PowerShell if WindowsApps blocks `rg`.
   macOS 使用 `python3`、正斜杠与 `~/.codex`，路径带空格时正确引用。如果确认桌面数据库位于其他位置，用 `--catalog-db <path>` 显式指定。预览 `desktop_catalog_found: false` 时，不能声称侧边栏已清理。
   On macOS use `python3`, forward slashes and `~/.codex`, quoting paths with spaces. If the desktop database is confirmed elsewhere, supply `--catalog-db <path>`. When preview reports `desktop_catalog_found: false`, do not claim sidebar cleanup.
3. 从技能目录运行脚本预览，检查计划、路径及 blockers。脚本只展示路径、ID 和数量，不输出对话正文。
   Run the bundled preview and inspect paths, counts, and blockers. Reports contain identities and counts, not conversation content.

   ```powershell
   python .\scripts\cleanup_threads.py --home 'E:\codex\.codex' 'codex://threads/11111111-1111-4111-8111-111111111111'
   ```

   上述 ID 是示例；替换为用户提供的目标。也可使用完整脚本路径。
   The UUID is synthetic; replace it with the user's target. An absolute script path also works.
4. 确认目标没有继续写入。若应用工具可用，检查目标状态；不得删除正在运行的任务。需要完全稳定的结果时，使用关闭全部 Codex 客户端后的外部终端。不要为了清理而自行结束整个应用。
   Ensure targets are not writing. Check their status through app tools when available; do not delete running tasks. For a stable offline cleanup, run in an external terminal after all Codex clients close. Do not forcibly terminate the application.
   macOS 关闭窗口不一定退出应用，稳定清理前使用 `⌘Q` 完全退出；Windows 确认托盘及其他使用同目录的客户端也已退出。
   Closing a macOS window may leave the app running; use `⌘Q` before offline cleanup. On Windows, also exit tray instances and other clients using the same home.
5. 用户已授权删除且预览无异常时加 `--apply`，在应用内传 `--protect-thread <当前任务UUID>`。独立终端中关闭客户端后才可用 `--offline`，该参数是人工状态声明，不负责关闭进程。多个目标作为多个位置参数传入。
   Apply an authorized, clean plan with `--apply` and `--protect-thread <current-task-UUID>` inside Codex. Use `--offline` only in an external terminal after closing clients; it asserts that condition and does not close processes. Pass multiple targets as separate positional arguments.
6. 脚本执行后会重新扫描；退出码非 0 时检查错误与残留，不要宣称成功。数据库锁、未知引用（例如自动化）、身份不一致或并发修改时停止，按 [存储说明 / storage map](references/storage-map.md) 排查，解决原因后对相同 ID 重试。不要清空数据库、全局缓存或改用关闭外键的方式绕过。
   The script rescans after applying. Nonzero exit means inspect errors or residuals before reporting success. On locks, unknown references (such as automations), identity mismatch, or concurrent writes, stop and consult the [storage map](references/storage-map.md). Retry the same IDs after resolving the cause; never wipe whole stores or disable foreign keys.
7. 单独运行 `--verify` 核验。报告实际删除数量和已知存储是否清空，并请用户重启刷新界面。桌面目录已同步清理时，预期不需要再点击归档；未经重启后验证，不保证界面一定消失。若再次出现，重新定位存储及写入进程，勿盲目重复归档。
   Run `--verify` separately. Report actual counts and known-store verification, then ask the user to restart to refresh the UI. Catalog cleanup is intended to avoid a second manual archive; do not claim restart behavior was verified unless observed. If entries return, investigate the store and writer.

## 范围与边界 / Scope and limits

- 删除源文件与专属记录；保留项目文件、子会话本体和其他会话正文中提及目标的文字。移除父子关系边，不递归删除子会话。
  Remove source files and owned records; retain project files, child threads, and mentions in other conversations. Remove relationship edges without recursively deleting children.
- 包括 `.codex-global-state.json.bak` 这份即时镜像；不新增对话备份。历史备份、日志、附件、云端副本、SQLite 空闲页/WAL 历史内容不属于本技能擦除范围。
  Include the immediate `.codex-global-state.json.bak` mirror without creating new conversation backups. Historical backups, logs, attachments, cloud copies, and forensic remnants in SQLite pages/WAL are outside scope.
- SQLite 使用事务和外键，文件替换使用 UTF-8 和内容变更检测；多个数据库与文件之间没有整体原子事务。异常可能留下部分完成状态，流程支持精确 ID 重试。
  SQLite uses transactions and foreign keys; file replacements use UTF-8 and content-change checks. There is no global transaction across databases and files. A failure may leave partial completion; retry by exact ID.

用户安装、操作步骤、技巧与注意事项见仓库的双语 `README.md`；技术存储细节仅在排查时读取 reference。
The repository's bilingual `README.md` covers installation, steps, tips, and cautions. Load the technical reference only when troubleshooting requires it.
