#!/usr/bin/env python3
"""Precisely remove selected local Codex threads. Python 3.10+, stdlib only."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import uuid


class CleanupError(RuntimeError):
    pass


DB_PATTERN = re.compile(r"(?:state|thread_history|queue|goals|memories)_\d+\.sqlite$")
# Children precede parents; identifiers are a maintained allowlist, never user SQL.
TABLES = {
    "thread_dynamic_tools": ("thread_id",),
    "thread_artifacts": ("thread_id",),
    "thread_spawn_edges": ("parent_thread_id", "child_thread_id"),
    "thread_items": ("thread_id",),
    "thread_realtime_items": ("thread_id",),
    "thread_turns": ("thread_id",),
    "thread_history_projection_state": ("thread_id",),
    "queued_items": ("thread_id",),
    "queued_thread_revisions": ("thread_id",),
    "thread_goal_continuation_deferrals": ("thread_id",),
    "thread_goals": ("thread_id",),
    "stage1_outputs": ("thread_id",),
    "local_thread_catalog": ("thread_id",),
    "local_thread_catalog_scan_entries": ("thread_id",),
    "thread_timeline_ledger": ("thread_id",),
    "inbox_items": ("thread_id",),
    "automation_runs": ("thread_id",),
    "threads": ("id",),
}
GLOBAL_FILES = (".codex-global-state.json", ".codex-global-state.json.bak")
INDEX_FILES = ("session_index.jsonl", "history.jsonl")


def thread_id(value: str) -> str:
    value = value.strip()
    if value.startswith("codex://threads/"):
        value = value[len("codex://threads/"):]
    try:
        result = str(uuid.UUID(value))
    except ValueError as exc:
        raise CleanupError(f"Invalid thread ID or link: {value}") from exc
    if value.lower() != result:
        raise CleanupError("Use a full hyphenated UUID or codex://threads/<UUID>.")
    return result


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise CleanupError(f"Path escapes selected Codex home: {path}")
    return resolved


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_state(value, ids: set[str]):
    """Drop exact identity keys/list entries; keep prose mentioning a target."""
    keys = ids | {"thread-workspace-state-v1:" + t for t in ids}
    if isinstance(value, dict):
        return {k: clean_state(v, ids) for k, v in value.items() if k not in keys}
    if isinstance(value, list):
        return [clean_state(v, ids) for v in value
                if not (isinstance(v, str) and v in ids)]
    return value


@dataclass
class Plan:
    home: Path
    ids: list[str]
    deletes: dict[Path, str] = field(default_factory=dict)
    rewrites: dict[Path, tuple[bytes, bytes]] = field(default_factory=dict)
    rows: list[tuple[Path, str, str, list[str], int]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    databases_checked: list[str] = field(default_factory=list)
    catalog_found: bool = False

    @property
    def remaining(self):
        return len(self.deletes) + len(self.rewrites) + sum(r[-1] for r in self.rows)

    def report(self):
        return {
            "home": str(self.home), "thread_ids": self.ids,
            "delete_files": [str(p) for p in self.deletes],
            "rewrite_files": [str(p) for p in self.rewrites],
            "database_rows": [{"database": str(p), "table": t, "count": n}
                              for p, t, _, _, n in self.rows],
            "blockers": self.blockers, "remaining_entries": self.remaining,
            "databases_checked": self.databases_checked,
            "desktop_catalog_found": self.catalog_found,
        }


def databases(home: Path, catalog_db: Path | None = None):
    result = set()
    for directory in (home, home / "sqlite"):
        if directory.exists():
            inside(directory, home)
            for p in directory.iterdir():
                if p.is_file() and (DB_PATTERN.fullmatch(p.name) or p.name == "codex-dev.db"):
                    result.add(inside(p, home))
    if catalog_db is not None:
        # An explicit path accommodates differing Windows/macOS app layouts.
        catalog_db = catalog_db.expanduser().resolve(strict=True)
        c = connect(catalog_db)
        try:
            cols = {r[1] for r in c.execute('PRAGMA table_info("local_thread_catalog")')}
            if not {"thread_id", "host_id"} <= cols:
                raise CleanupError("--catalog-db is not a recognized Codex desktop catalog.")
        finally:
            c.close()
        result.add(catalog_db)
    return sorted(result)


def connect(path: Path, write=False):
    # mode=rw prevents silently creating an empty database on a wrong path.
    c = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"),
                        uri=True, timeout=5)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def condition(keys, ids):
    marks = ",".join("?" for _ in ids)
    where = " OR ".join(f"{quote(k)} IN ({marks})" for k in keys)
    return where, list(ids) * len(keys)


def scan_db(c, path: Path, plan: Plan):
    schema = {t: {r[1] for r in c.execute(f"PRAGMA table_info({quote(t)})")}
              for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    plan.databases_checked.append(str(path))
    plan.catalog_found |= "local_thread_catalog" in schema
    for table, keys in TABLES.items():
        if table not in schema:
            continue
        if not set(keys) <= schema[table]:
            plan.blockers.append(f"Unsupported schema: {path.name}/{table}")
            continue
        where, params = condition(keys, plan.ids)
        n = c.execute(f"SELECT count(*) FROM {quote(table)} WHERE {where}", params).fetchone()[0]
        if n:
            # Local data only: never delete another host's catalog record.
            if "host_id" in schema[table]:
                hosts = c.execute(f"SELECT DISTINCT host_id FROM {quote(table)} WHERE {where}", params)
                if any(h != "local" for (h,) in hosts):
                    plan.blockers.append(f"Non-local host matched in {path.name}/{table}")
            plan.rows.append((path, table, where, params, n))
    for table, cols in schema.items():
        if table not in TABLES:
            keys = sorted(k for k in cols if k == "thread_id" or k.endswith("_thread_id"))
            # Migration cursors are global scan state, not thread ownership.
            if table == "rollout_migration_state":
                continue
            if keys:
                where, params = condition(keys, plan.ids)
                n = c.execute(f"SELECT count(*) FROM {quote(table)} WHERE {where}", params).fetchone()[0]
                if n:
                    plan.blockers.append(f"Unmanaged thread reference: {path.name}/{table} ({n} rows)")
        for fk in c.execute(f"PRAGMA foreign_key_list({quote(table)})"):
            if fk[2] in TABLES and table not in TABLES:
                plan.blockers.append(f"Review unknown dependent table: {path.name}/{table}")
    touched = {t for p, t, _, _, _ in plan.rows if p == path}
    triggers = c.execute("SELECT name,tbl_name FROM sqlite_master WHERE type='trigger'")
    for name, table in triggers:
        if table in touched:
            plan.blockers.append(f"Review trigger before deletion: {path.name}/{name}")
    if "local_thread_catalog" in touched:
        if "catalog_revision" not in schema.get("local_thread_catalog_metadata", set()):
            plan.blockers.append("Desktop catalog revision schema is missing.")
        elif c.execute("SELECT count(*) FROM local_thread_catalog_metadata WHERE id=1").fetchone()[0] != 1:
            plan.blockers.append("Desktop catalog revision row is missing.")
    if {"id", "rollout_path"} <= schema.get("threads", set()):
        where, params = condition(["id"], plan.ids)
        for t, raw in c.execute(f"SELECT id,rollout_path FROM threads WHERE {where}", params):
            # Database paths may traverse a Windows junction; compare resolved paths.
            p = Path(raw)
            if not p.is_absolute():
                plan.blockers.append(f"Non-absolute rollout path for {t}")
                continue
            rp = inside(p, plan.home)
            allowed = any(rp.is_relative_to((plan.home / d).resolve())
                          for d in ("sessions", "archived_sessions"))
            if not allowed or not rp.name.endswith("-" + t + ".jsonl"):
                plan.blockers.append(f"Unexpected rollout location for {t}")
            elif rp.exists():
                plan.deletes[rp] = digest(rp)


def scan_files(plan: Plan):
    home, ids = plan.home, set(plan.ids)
    for folder in ("sessions", "archived_sessions"):
        root = home / folder
        if not root.exists():
            continue
        inside(root, home)
        # Find orphaned or zero-filled rollouts even when the DB row is absent.
        for p in root.rglob("rollout-*.jsonl"):
            if any(p.name.endswith("-" + t + ".jsonl") for t in ids):
                rp = inside(p, root)
                if not any(rp.name.endswith("-" + t + ".jsonl") for t in ids):
                    raise CleanupError(f"Resolved rollout identity differs from requested ID: {p.name}")
                plan.deletes[rp] = digest(rp)
    for p in plan.deletes:
        with p.open("rb") as stream:
            first = stream.readline(65536)
        try:
            meta = json.loads(first)
        except (ValueError, UnicodeError):
            continue  # A broken header is the original use case.
        if isinstance(meta, dict) and meta.get("type") == "session_meta":
            payload = meta.get("payload")
            identity = payload.get("id") if isinstance(payload, dict) else None
            if identity and (not isinstance(identity, str) or identity not in ids
                             or not p.name.endswith("-" + identity + ".jsonl")):
                plan.blockers.append(f"Rollout filename/header identity mismatch: {p.name}")
    for name in GLOBAL_FILES + INDEX_FILES:
        p = home / name
        if not p.exists():
            continue
        inside(p, home)
        if p.is_symlink():
            raise CleanupError(f"Refusing to replace a linked state file: {p}")
        old = p.read_bytes()
        if name in GLOBAL_FILES:
            data = json.loads(old.decode("utf-8-sig"))
            new_data = clean_state(data, ids)
            if data == new_data:
                continue
            new = (json.dumps(new_data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        else:
            keep = []
            for line in old.splitlines(keepends=True):
                try:
                    entry = json.loads(line.decode("utf-8-sig"))
                except (ValueError, UnicodeError):
                    keep.append(line)
                    continue
                if not isinstance(entry, dict) or not any(
                    isinstance(entry.get(k), str) and entry[k] in ids
                    for k in ("id", "thread_id", "session_id")
                ):
                    keep.append(line)
            new = b"".join(keep)
            if old == new:
                continue
        plan.rewrites[p] = (old, new)


def inspect(home: Path, ids: list[str], connections=None, catalog_db=None):
    plan = Plan(home, ids)
    for db in databases(home, catalog_db):
        if connections is not None:
            scan_db(connections[db], db, plan)
        else:
            with ExitStack() as stack:
                c = connect(db)
                stack.callback(c.close)
                scan_db(c, db, plan)
    scan_files(plan)
    return plan


def check_files(plan):
    for p, sha in plan.deletes.items():
        inside(p, plan.home)
        if digest(p) != sha:
            raise CleanupError(f"Rollout changed; stop the target task before retrying: {p.name}")
    for p, (old, _) in plan.rewrites.items():
        inside(p, plan.home)
        if p.read_bytes() != old:
            raise CleanupError(f"State changed concurrently; close Codex and retry: {p.name}")


def apply(home, ids, catalog_db=None):
    with ExitStack() as stack:
        connections = {}
        for db in databases(home, catalog_db):
            c = connect(db, write=True)
            stack.callback(c.close)  # Rolls back an uncommitted transaction.
            c.execute("BEGIN IMMEDIATE")
            connections[db] = c
        plan = inspect(home, ids, connections, catalog_db)
        if plan.blockers:
            raise CleanupError("; ".join(plan.blockers))
        check_files(plan)
        for db, table, where, params, _ in plan.rows:
            connections[db].execute(f"DELETE FROM {quote(table)} WHERE {where}", params)
        for db, c in connections.items():
            if any(p == db and t == "local_thread_catalog" for p, t, *_ in plan.rows):
                c.execute("UPDATE local_thread_catalog_metadata SET catalog_revision=catalog_revision+1 WHERE id=1")
        check_files(plan)
        # Databases and files are not one atomic transaction. On partial failure,
        # report it, inspect again, and retry the same IDs after stopping writers.
        for c in connections.values():
            c.commit()
        for p, (old, new) in plan.rewrites.items():
            fd, tmp = tempfile.mkstemp(prefix=p.name + ".cleanup-", dir=p.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(new)
                    stream.flush()
                    os.fsync(stream.fileno())
                if p.read_bytes() != old:
                    raise CleanupError(f"State changed concurrently: {p.name}")
                os.replace(tmp, p)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        for p, sha in plan.deletes.items():
            inside(p, home)
            if digest(p) != sha:
                raise CleanupError(f"Rollout changed during deletion: {p.name}")
            p.unlink()
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("threads", nargs="+", help="Exact UUIDs or codex://threads/<UUID> links")
    parser.add_argument("--home", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    parser.add_argument("--catalog-db", type=Path, help="Explicit Codex desktop catalog path when stored outside the detected home")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Delete the specified threads; default is read-only")
    mode.add_argument("--verify", action="store_true", help="Read-only check; exit 2 if entries remain")
    parser.add_argument("--protect-thread", action="append", default=[], help="Never delete this task UUID; repeatable")
    parser.add_argument("--offline", action="store_true", help="Assert that all Codex clients using this home are closed")
    args = parser.parse_args(argv)
    try:
        ids = sorted({thread_id(t) for t in args.threads})
        protected = {thread_id(t) for t in args.protect_thread}
        if os.environ.get("CODEX_THREAD_ID"):
            protected.add(thread_id(os.environ["CODEX_THREAD_ID"]))
        if protected.intersection(ids):
            raise CleanupError("Refusing to delete the current/protected task. Use a separate task or external terminal.")
        if args.apply and not (protected or args.offline):
            raise CleanupError("Supply --protect-thread <current-task-id>, or run outside Codex with --offline after closing all clients.")
        home = args.home.expanduser().resolve(strict=True)
        if not home.is_dir() or not any((home / name).exists() for name in ("sessions", "archived_sessions", "sqlite", ".codex-global-state.json")):
            raise CleanupError("The selected directory does not look like a Codex data home.")
        plan = inspect(home, ids, catalog_db=args.catalog_db)
        if args.apply:
            if plan.blockers:
                raise CleanupError("; ".join(plan.blockers))
            changed = apply(home, ids, args.catalog_db)
            plan = inspect(home, ids, catalog_db=args.catalog_db)
            result = {"mode": "apply", "changed": changed.report(), "verification": plan.report()}
        else:
            result = {"mode": "verify" if args.verify else "preview", **plan.report()}
        result["scope"] = "Known local stores only; no cloud deletion, log/backup erasure or UI restart verification."
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if plan.blockers or ((args.apply or args.verify) and plan.remaining) else 0
    except (CleanupError, OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"error": str(exc), "next_step": "Inspect again before retrying. An apply failure can leave partial cleanup."}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
