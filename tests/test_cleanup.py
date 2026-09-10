"""Behavior tests use synthetic data only; never inspect the real Codex home."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "codex-session-cleanup" / "scripts" / "cleanup_threads.py"
spec = importlib.util.spec_from_file_location("cleanup", SCRIPT)
cleanup = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cleanup
spec.loader.exec_module(cleanup)

TARGET = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
MISSING = "33333333-3333-4333-8333-333333333333"


class CleanupTests(unittest.TestCase):
    def setUp(self):
        # Generated files stay in repository work/, which is ignored by Git.
        work = SCRIPT.parents[2] / "work"
        work.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="cleanup-test-", dir=work)
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve() / "中文 data"
        self.home.mkdir()
        (self.home / "sessions").mkdir()
        (self.home / "sqlite").mkdir()
        self.paths = {}
        for t in (TARGET, OTHER):
            p = self.home / "sessions" / ("rollout-example-" + t + ".jsonl")
            # Reproduce the original zero-filled rollout bug.
            p.write_bytes(b"\0" * 64 if t == TARGET else b'kept original bytes\r\n')
            self.paths[t] = p
        self.state = self.home / "state_5.sqlite"
        with self.db(self.state) as c:
            c.executescript('''
                CREATE TABLE threads(id TEXT PRIMARY KEY, rollout_path TEXT);
                CREATE TABLE thread_dynamic_tools(thread_id TEXT REFERENCES threads(id) ON DELETE CASCADE, value TEXT);
                CREATE TABLE thread_spawn_edges(parent_thread_id TEXT, child_thread_id TEXT);
            ''')
            for t, p in self.paths.items():
                c.execute("INSERT INTO threads VALUES (?,?)", (t, str(p)))
                c.execute("INSERT INTO thread_dynamic_tools VALUES (?,?)", (t, "工具"))
            c.execute("INSERT INTO thread_spawn_edges VALUES (?,?)", (TARGET, OTHER))
        self.catalog = self.home / "sqlite" / "codex-dev.db"
        with self.db(self.catalog) as c:
            c.executescript('''
                CREATE TABLE local_thread_catalog(host_id TEXT, thread_id TEXT);
                CREATE TABLE local_thread_catalog_metadata(id INTEGER PRIMARY KEY, catalog_revision INTEGER);
                INSERT INTO local_thread_catalog_metadata VALUES(1,7);
                CREATE TABLE local_thread_catalog_scan_entries(host_id TEXT, thread_id TEXT);
                CREATE TABLE thread_timeline_ledger(host_id TEXT, thread_id TEXT, payload_json TEXT);
                CREATE TABLE inbox_items(thread_id TEXT, description TEXT);
                CREATE TABLE automation_runs(thread_id TEXT, status TEXT);
                CREATE TABLE automations(target_thread_id TEXT, status TEXT);
            ''')
            for t in (TARGET, OTHER):
                c.execute("INSERT INTO local_thread_catalog VALUES ('local',?)", (t,))
                c.execute("INSERT INTO local_thread_catalog_scan_entries VALUES ('local',?)", (t,))
                c.execute("INSERT INTO thread_timeline_ledger VALUES ('local',?,'{}')", (t,))
                c.execute("INSERT INTO inbox_items VALUES (?,'kept if other')", (t,))
                c.execute("INSERT INTO automation_runs VALUES (?,'complete')", (t,))
        self.global_file = self.home / ".codex-global-state.json"
        self.global_file.write_text(json.dumps({
            "thread-project-assignments": {TARGET: "A", OTHER: "B"},
            "electron-persisted-atom-state": {
                "thread-workspace-state-v1:" + TARGET: {"x": 1},
                "prompt-history": {OTHER: ["请删除 " + TARGET]},
                "heartbeat-thread-permissions-by-id": {TARGET: True},
            }, "pinned": [TARGET, OTHER], "other_setting": "保留中文"
        }, ensure_ascii=False), encoding="utf-8")
        (self.home / ".codex-global-state.json.bak").write_bytes(self.global_file.read_bytes())
        self.keep_line = (json.dumps({"id": OTHER, "text": "保留提及 " + TARGET}, ensure_ascii=False) + "\r\n").encode("utf-8")
        (self.home / "session_index.jsonl").write_bytes(
            (json.dumps({"id": TARGET}) + "\n").encode() + self.keep_line + b"malformed line\n")
        (self.home / "history.jsonl").write_text(json.dumps({"session_id": TARGET}) + "\n", encoding="utf-8")
        (self.home / "auth.json").write_bytes(b"untouched credentials placeholder")
        (self.home / "historical-backup.json").write_text(TARGET, encoding="utf-8")

    @contextlib.contextmanager
    def db(self, path):
        c = sqlite3.connect(path)
        try:
            with c:
                yield c
        finally:
            c.close()

    def cli(self, *args, current=""):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"CODEX_THREAD_ID": current}), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cleanup.main(["--home", str(self.home), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}

    def test_preview_is_read_only_and_has_no_content(self):
        before = self.snapshot()
        code, out, err = self.cli(TARGET)
        self.assertEqual(code, 0, err)
        self.assertNotIn("请删除", out)
        self.assertNotIn("工具", out)
        self.assertEqual(before, self.snapshot())
        self.assertGreater(json.loads(out)["remaining_entries"], 0)

    def test_precise_cleanup_catalog_and_idempotence(self):
        other_bytes = self.paths[OTHER].read_bytes()
        code, out, err = self.cli("--apply", "--offline", TARGET)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["verification"]["remaining_entries"], 0)
        self.assertFalse(self.paths[TARGET].exists())
        self.assertEqual(self.paths[OTHER].read_bytes(), other_bytes)
        with self.db(self.state) as c:
            self.assertEqual(c.execute("SELECT id FROM threads").fetchall(), [(OTHER,)])
            self.assertEqual(c.execute("SELECT count(*) FROM thread_spawn_edges").fetchone()[0], 0)
            self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(), [])
        with self.db(self.catalog) as c:
            self.assertEqual(c.execute("SELECT catalog_revision FROM local_thread_catalog_metadata").fetchone()[0], 8)
            self.assertEqual(c.execute("SELECT thread_id FROM local_thread_catalog").fetchall(), [(OTHER,)])
        d = json.loads(self.global_file.read_bytes())
        self.assertEqual(d["other_setting"], "保留中文")
        self.assertEqual(d["electron-persisted-atom-state"]["prompt-history"][OTHER], ["请删除 " + TARGET])
        self.assertEqual(d["pinned"], [OTHER])
        self.assertEqual((self.home / "session_index.jsonl").read_bytes(), self.keep_line + b"malformed line\n")
        self.assertEqual((self.home / "historical-backup.json").read_text(), TARGET)
        self.assertEqual((self.home / "auth.json").read_bytes(), b"untouched credentials placeholder")
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 0)
        with self.db(self.catalog) as c:
            self.assertEqual(c.execute("SELECT catalog_revision FROM local_thread_catalog_metadata").fetchone()[0], 8)
        self.assertEqual(self.cli("--verify", TARGET)[0], 0)

    def test_batch_links_and_duplicate_ids(self):
        code, out, err = self.cli("--apply", "--offline", "codex://threads/" + TARGET, TARGET, OTHER)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(json.loads(out)["changed"]["thread_ids"]), 2)
        self.assertFalse(self.paths[OTHER].exists())

    def test_rejects_current_and_protected_ids(self):
        before = self.snapshot()
        for argv, current in [(["--apply", "--offline", TARGET], TARGET),
                              (["--apply", "--protect-thread", TARGET, TARGET], "")]:
            code, _, _ = self.cli(*argv, current=current)
            self.assertEqual(code, 1)
        self.assertEqual(before, self.snapshot())

    def test_apply_requires_current_protection_or_offline_assertion(self):
        before = self.snapshot()
        self.assertEqual(self.cli("--apply", TARGET)[0], 1)
        self.assertEqual(before, self.snapshot())

    def test_verify_missing_and_remaining(self):
        self.assertEqual(self.cli("--verify", TARGET)[0], 2)
        before = self.snapshot()
        self.assertEqual(self.cli("--verify", MISSING)[0], 0)
        self.assertEqual(before, self.snapshot())

    def test_invalid_ids(self):
        before = self.snapshot()
        for t in ("../sessions", "1111", TARGET + "/extra", "https://example.com/" + TARGET):
            self.assertEqual(self.cli("--apply", "--offline", t)[0], 1)
        self.assertEqual(before, self.snapshot())

    def test_unknown_reference_blocks_before_mutation(self):
        with self.db(self.state) as c:
            c.execute("CREATE TABLE future_links(owner_thread_id TEXT)")
            c.execute("INSERT INTO future_links VALUES (?)", (TARGET,))
        before = self.snapshot()
        self.assertEqual(self.cli(TARGET)[0], 2)
        code, _, err = self.cli("--apply", "--offline", TARGET)
        self.assertEqual(code, 1)
        self.assertIn("future_links", err)
        self.assertEqual(before, self.snapshot())

    def test_automation_reference_blocks(self):
        with self.db(self.catalog) as c:
            c.execute("INSERT INTO automations VALUES (?,'ACTIVE')", (TARGET,))
        before = self.snapshot()
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 1)
        self.assertEqual(before, self.snapshot())

    def test_foreign_catalog_host_blocks(self):
        with self.db(self.catalog) as c:
            c.execute("UPDATE local_thread_catalog SET host_id='ssh' WHERE thread_id=?", (TARGET,))
        before = self.snapshot()
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 1)
        self.assertEqual(before, self.snapshot())

    def test_rollout_path_outside_home_blocks(self):
        outside = self.home.parent / ("rollout-example-" + TARGET + ".jsonl")
        outside.write_bytes(b"do not delete")
        with self.db(self.state) as c:
            c.execute("UPDATE threads SET rollout_path=? WHERE id=?", (str(outside), TARGET))
        before = self.snapshot()
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 1)
        self.assertEqual(outside.read_bytes(), b"do not delete")
        self.assertEqual(before, self.snapshot())

    def test_mismatched_rollout_identity_blocks(self):
        self.paths[TARGET].write_text(json.dumps({"type": "session_meta", "payload": {"id": OTHER}}) + "\n")
        before = self.snapshot()
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 1)
        self.assertEqual(before, self.snapshot())

    def test_changed_file_stops_snapshot_application(self):
        plan = cleanup.inspect(self.home, [TARGET])
        self.paths[TARGET].write_bytes(b"a running task wrote this")
        with self.assertRaises(cleanup.CleanupError):
            cleanup.check_files(plan)
        plan = cleanup.inspect(self.home, [TARGET])
        self.global_file.write_text('{"changed":true}', encoding="utf-8")
        with self.assertRaises(cleanup.CleanupError):
            cleanup.check_files(plan)

    def test_malformed_state_stops_before_sql_deletion(self):
        self.global_file.write_text('{broken', encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 1)
        self.assertEqual(before, self.snapshot())

    def test_trigger_blocks(self):
        with self.db(self.state) as c:
            c.execute("CREATE TRIGGER future_delete AFTER DELETE ON threads BEGIN DELETE FROM thread_dynamic_tools; END")
        before = self.snapshot()
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 1)
        self.assertEqual(before, self.snapshot())

    def test_history_queue_goals_and_legacy_databases(self):
        for name, tables in {
            "thread_history_1.sqlite": ["thread_turns", "thread_items", "thread_realtime_items", "thread_history_projection_state"],
            "queue_1.sqlite": ["queued_items", "queued_thread_revisions"],
            "goals_1.sqlite": ["thread_goal_continuation_deferrals", "thread_goals"],
            "sqlite/memories_1.sqlite": ["stage1_outputs"],
        }.items():
            with self.db(self.home / name) as c:
                for table in tables:
                    c.execute(f"CREATE TABLE {table}(thread_id TEXT, payload TEXT)")
                    c.executemany(f"INSERT INTO {table} VALUES (?,'data')", [(TARGET,), (OTHER,)])
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 0)
        self.assertEqual(cleanup.inspect(self.home, [TARGET]).remaining, 0)
        with self.db(self.home / "thread_history_1.sqlite") as c:
            self.assertEqual(c.execute("SELECT thread_id FROM thread_items").fetchall(), [(OTHER,)])

    def test_orphan_archived_file_removed(self):
        archived = self.home / "archived_sessions"
        archived.mkdir()
        p = archived / ("rollout-orphan-" + MISSING + ".jsonl")
        p.write_bytes(b"\0" * 100)
        self.assertEqual(self.cli("--apply", "--offline", MISSING)[0], 0)
        self.assertFalse(p.exists())
        self.assertTrue(self.paths[TARGET].exists())

    def test_unknown_fk_dependency_blocks(self):
        with self.db(self.state) as c:
            c.execute("CREATE TABLE dependent(owner TEXT REFERENCES threads(id) ON DELETE CASCADE)")
            c.execute("INSERT INTO dependent VALUES (?)", (TARGET,))
        before = self.snapshot()
        self.assertEqual(self.cli("--apply", "--offline", TARGET)[0], 1)
        self.assertEqual(before, self.snapshot())

    def test_alternate_catalog_location(self):
        relocated = self.home.parent / "Application Support 示例" / "catalog.db"
        relocated.parent.mkdir()
        self.catalog.rename(relocated)
        code, out, err = self.cli("--catalog-db", str(relocated), "--apply", "--offline", TARGET)
        self.assertEqual(code, 0, err)
        self.assertTrue(json.loads(out)["verification"]["desktop_catalog_found"])
        with self.db(relocated) as c:
            self.assertEqual(c.execute("SELECT thread_id FROM local_thread_catalog").fetchall(), [(OTHER,)])

    def test_explicit_catalog_requires_supported_schema(self):
        unrelated = self.home.parent / "not-codex.db"
        with self.db(unrelated) as c:
            c.execute("CREATE TABLE important(id TEXT)")
            c.execute("INSERT INTO important VALUES (?)", (TARGET,))
        before = self.snapshot()
        original = unrelated.read_bytes()
        self.assertEqual(self.cli("--catalog-db", str(unrelated), "--apply", "--offline", TARGET)[0], 1)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(original, unrelated.read_bytes())

    def test_missing_catalog_is_reported(self):
        self.catalog.unlink()
        code, out, err = self.cli(TARGET)
        self.assertEqual(code, 0, err)
        self.assertFalse(json.loads(out)["desktop_catalog_found"])

    def test_symlink_home_resolves_to_same_store(self):
        alias = self.home.parent / "home-alias"
        try:
            alias.symlink_to(self.home, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not allow unprivileged symlinks")
        try:
            with patch.dict(os.environ, {"CODEX_THREAD_ID": ""}), contextlib.redirect_stdout(io.StringIO()):
                code = cleanup.main(["--home", str(alias), "--apply", "--offline", TARGET])
            self.assertEqual(code, 0)
            self.assertFalse(self.paths[TARGET].exists())
        finally:
            alias.unlink()

    def test_orphan_symlink_cannot_delete_another_thread(self):
        alias = self.home / "sessions" / ("rollout-orphan-" + MISSING + ".jsonl")
        try:
            alias.symlink_to(self.paths[OTHER])
        except OSError:
            self.skipTest("Host does not allow unprivileged symlinks")
        try:
            kept = self.paths[OTHER].read_bytes()
            self.assertEqual(self.cli("--apply", "--offline", MISSING)[0], 1)
            self.assertEqual(self.paths[OTHER].read_bytes(), kept)
        finally:
            alias.unlink()


if __name__ == "__main__":
    unittest.main()
