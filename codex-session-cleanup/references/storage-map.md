# 存储与排障 / Storage and troubleshooting

此流程根据本机观察到的 Codex 数据布局整理，属于内部格式维护，不是官方稳定删除 API。适用脚本能识别的表结构；升级导致未知匹配引用、触发器或外键依赖时先审查再适配。
This workflow follows an observed local Codex layout. It maintains internal storage, not an official stable deletion API. Unknown matching references, triggers, or foreign-key dependencies require review after upgrades.

## 为什么只删文件还不够 / Why deleting only the file is insufficient

损坏的 rollout 可能导致应用报告找不到可读任务，但 `threads` 行仍存在。删除该行和文件后，桌面应用的 `local_thread_catalog` 仍可能保留条目。这个独立目录是“重启后还要再手动归档”的关键排查位置。
A damaged rollout can make the app report no readable task while its `threads` row survives. Removing that row and file can still leave an independent `local_thread_catalog` entry. This catalog is the key location to inspect when a restart still requires another manual archive.

| 位置 / Location | 处理 / Treatment |
| --- | --- |
| `sessions`、`archived_sessions` | 删除文件名精确以目标 UUID 结尾的 rollout；有元数据时核对头部 ID。Delete exact-ID rollouts; check the header identity when present. |
| `state_<version>.sqlite` | 清理 `threads`、动态工具、产物、父子关系边；子任务本体保留。Remove thread rows, tools, artifacts and relationship edges; retain child tasks. |
| `thread_history_<version>.sqlite` | 清理 turns、items、realtime items、projection state。Remove owned history and projection rows. |
| `queue_<version>.sqlite` | 清理排队项与修订记录。Remove queued items and revision rows. |
| `goals_<version>.sqlite`、`memories_<version>.sqlite` | 清理目标及专属记忆输出。Remove goals and thread-owned memory output. |
| `sqlite\codex-dev.db` | 清理 `local_thread_catalog`、scan entries、timeline ledger、inbox items、automation run history；删除目录条目时递增 `catalog_revision`。Remove owned desktop catalog/scan/timeline/inbox/run-history rows and bump the catalog revision. |
| 数据目录与 `sqlite` 子目录 / Home and `sqlite` | 扫描已知版本化数据库；缺失文件不会新建。Discover recognized versioned databases; never create missing databases. |
| `.codex-global-state.json` 及 `.bak` | 移除精确 ID 的字典键、数组成员和专属 workspace 键，保留正文中的提及。Remove exact identity keys/list members/workspace keys; preserve prose mentions. |
| `session_index.jsonl`、`history.jsonl` | 按 `id`、`thread_id`、`session_id` 精确过滤；其他行逐字节保留。Filter exact identity fields; preserve other lines byte-for-byte. |

## 失败分支 / Failure cases

| 情况 / Symptom | 下一步 / Next step |
| --- | --- |
| `Unmanaged thread reference` | 读取指定表结构并判断语义。若自动化指向该任务，用受支持工具处理该自动化且遵守用户授权；不要直接删整个自动化配置。Inspect the named schema. Resolve a linked automation through supported tools within user authorization; do not wipe automation configuration. |
| `Non-local host matched` | 确认任务归属，转到对应主机；本机脚本拒绝删除远程目录记录。Use the correct host; the script refuses non-local catalog entries. |
| `Path escapes` / 身份不一致 | 核对 `--home`、junction 与原始 rollout 路径，不要删除越界文件。Verify the home, junction and source path; never delete the escaped file. |
| `database is locked` | 停止重试，关闭使用该目录的客户端后从外部终端执行。Stop retrying; close clients using the home and run from an external terminal. |
| 文件并发变更 / Concurrent file change | 全局状态可能被桌面内存覆盖；关闭客户端后重新预览、执行和核验。Desktop memory may rewrite state; close clients, then preview, apply and verify again. |
| 执行中失败 / Apply fails partway | 先 `--verify` 确认已完成和残留，解决锁或写入问题后对同一批 ID 重试。Verify residuals first, resolve the failure, then retry the same IDs. |
| 核验 0 条但界面仍显示 / Zero residuals but visible UI | 重启刷新后再验证；若持久复现，查找新增存储或写入者，不清空全部应用缓存。Restart, then verify again; persistent recurrence needs investigation of a new store/writer, not a whole-cache wipe. |

## 已知边界 / Known limits

Windows 默认数据目录是 `%USERPROFILE%\.codex`，macOS 默认是 `~/.codex`，两者都可被 `CODEX_HOME` 或 `--home` 覆盖。不要把 macOS 的 `~/Library/Application Support`、Windows 的 AppData 或应用沙盒容器当作默认删除根目录。若确认客户端的 Codex 桌面目录数据库在数据根目录以外，可通过 `--catalog-db` 指定精确文件；脚本先检查 `local_thread_catalog` 身份字段才会接受。
The default home is `%USERPROFILE%\.codex` on Windows and `~/.codex` on macOS; `CODEX_HOME` or `--home` overrides either. Do not use macOS Application Support, Windows AppData, or app sandbox containers as blanket deletion roots. If a client's Codex catalog is confirmed outside the home, pass that exact file with `--catalog-db`; its identity columns must match before acceptance.

预览包含 `databases_checked` 与 `desktop_catalog_found`。未发现目录时，源文件核验为零也不能证明侧边栏已同步。若无法找到受支持的目录，报告范围限制。ChatGPT Work 可以执行技能指令或转交本机脚本；是否能直接操作由实际工具与权限决定。
Preview includes `databases_checked` and `desktop_catalog_found`. Without a recognized catalog, zero rollout residuals do not establish sidebar synchronization. Report the limitation if the catalog cannot be located. ChatGPT Work can follow the instructions or hand off the local script; direct execution depends on its actual tools and permissions.

运行中的应用可能在核验后写回内存状态。脚本的哈希检查和 JSON 原子替换只能缩小竞态窗口，不能锁住 Electron 内存；`--offline` 是用户声明，并非进程检测器。稳定路径是关闭所有使用该数据目录的客户端，在外部终端清理，再启动应用。
A running app can rewrite in-memory state after verification. Hash checks and atomic JSON replacement reduce races but cannot lock Electron memory. `--offline` is a user assertion, not a process detector. The stable path is to close all clients using the home, clean from an external terminal, and reopen.

脚本不会删除日志、历史备份、附件、可视化、项目目录、worktree、凭据或云端副本，也不会执行 VACUUM 或清空 WAL。它完成已知存储的逻辑删除，不承诺取证级不可恢复。
The script does not remove logs, historical backups, attachments, visualizations, projects, worktrees, credentials or cloud copies, nor vacuum databases or truncate WAL files. It performs logical deletion from known stores, not forensic erasure.
