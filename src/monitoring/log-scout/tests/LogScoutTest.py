#!/usr/bin/env python3
"""Synthetic behavior, persistence, terminal interaction, and installation checks."""

from __future__ import annotations

import copy
import bz2
import json
import os
import pty
import selectors
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
REPOSITORY = MODULE.parents[2]
sys.path.insert(0, str(MODULE / "scripts"))
from LogScoutCache import LogScoutCache
from log_scout_rules import classify, sanitize
from log_scout_scan import scan
from log_scout_sources import journal_output, read_file, read_journal


class LogScoutTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.log = self.root / "sample.log"
        self.log.write_text("INFO all ready\nERROR connection refused on port 123\n"
                            "ERROR connection refused on port 456\nWARNING disk full\n"
                            "CRITICAL out of memory\nERROR authentication password=synthetic-secret\n")
        self.cache = LogScoutCache(self.root / "cache")
        self.environment = dict(os.environ, LOG_SCOUT_CACHE_DIR=str(self.cache.directory),
                                PYTHONDONTWRITEBYTECODE="1", HOME=str(self.root / "home"))

    def run_cli(self, *args, expected=0, executable=None):
        result = subprocess.run([str(executable or MODULE / "scripts/log-scout"), *map(str, args)],
                                env=self.environment, capture_output=True, text=True, cwd=self.root, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def sample(self):
        return scan([self.log], False, "24 hours ago", 5000)

    def test_scan_reopen_and_drilldown(self):
        result = self.run_cli("scan", "--file", self.log, "--json")
        data = json.loads(result.stdout)
        self.assertEqual(data["examined"], 6)
        self.assertEqual(data["matches"], 5)
        self.assertEqual(data["categories"]["network"], 2)
        self.assertEqual(len(data["groups"]), 4)
        self.assertNotIn("synthetic-secret", result.stdout)
        self.log.unlink()
        self.assertIn("network", self.run_cli("summary").stdout)
        self.assertIn("2 occurrences", self.run_cli("details", "network", "--group", "1").stdout)
        self.assertIn(data["id"], self.run_cli("history").stdout)
        self.assertEqual(self.cache.load()["id"], data["id"])
        self.assertEqual(self.cache.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(next(self.cache.directory.glob("*.json")).stat().st_mode & 0o777, 0o600)

    def test_classification_priority_and_redaction(self):
        self.assertIsNone(classify("error count zero", "6"))
        self.assertEqual(classify("disk full", "2"), ("storage", "critical"))
        self.assertEqual(classify("ERROR failed password", "invalid"), ("security", "error"))
        text = sanitize('ERROR token=abc password="a b" Authorization: Bearer xyz '
                        'https://user:pass@example.test/path?token=xyz alice@example.test\x1b[31m\u202e')
        for secret in ('abc', 'a b', 'xyz', 'user:pass', 'alice@example.test', '\x1b', '\u202e'):
            self.assertNotIn(secret, text)

    def test_partial_and_failed_scan_preserve_history(self):
        self.run_cli("scan", "--file", self.log, "--file", self.root / "missing", expected=2)
        latest = self.cache.load()
        self.assertTrue(latest["partial"])
        self.assertTrue(latest["sources"][1]["error"])
        self.run_cli("scan", "--file", self.root / "missing", expected=1)
        self.assertEqual(self.cache.load()["id"], latest["id"])
        self.run_cli("scan", "--file", self.log, "--limit", "1", expected=2)
        self.assertEqual(self.cache.load()["examined"], 1)
        self.run_cli("scan", "--file", self.log, "--limit", "0", expected=1)
        self.run_cli("details", "network", "--group", "999", expected=1)
        self.run_cli("summary", "--scan", "../../escape", expected=1)

    def test_file_bounds_and_special_files(self):
        with patch("log_scout_sources.MAX_BYTES", 30):
            records, warnings = read_file(self.log, 100)
        self.assertTrue(warnings)
        self.assertLessEqual(len(records), 1)
        link = self.root / "link"
        link.symlink_to(self.log)
        self.run_cli("scan", "--file", link, expected=1)
        pipe = self.root / "pipe"
        os.mkfifo(pipe)
        self.run_cli("scan", "--file", pipe, expected=1)
        self.run_cli("scan", "--file", self.root, expected=1)
        self.log.write_bytes(b"compressed\0data")
        self.run_cli("scan", "--file", self.log, expected=1)
        self.log.write_bytes(bz2.compress(b"ERROR connection failed\n"))
        self.run_cli("scan", "--file", self.log, expected=1)

    def test_journal_priority_limit_and_diagnostics(self):
        entries = [{"MESSAGE": "ERROR ignored", "PRIORITY": "6"},
                   {"MESSAGE": "connection refused", "PRIORITY": "3", "_SYSTEMD_UNIT": "demo.service"}]
        payload = b"\n".join(json.dumps(entry).encode() for entry in entries)
        with patch("log_scout_sources.journal_output", return_value=(payload, "limited permissions")):
            data = scan([], True, "2 hours ago", 10)
            self.assertEqual(data["matches"], 1)
            self.assertTrue(data["partial"])
            self.assertEqual(data["groups"][0]["unit"], "demo.service")
            records, warnings = read_journal(1, "2 hours ago")
            self.assertEqual(len(records), 1)
            self.assertEqual(len(warnings), 2)
        with patch("log_scout_sources.journal_output", return_value=(b"not json", "")):
            with self.assertRaisesRegex(RuntimeError, "No source"):
                scan([], True, "today", 10)

    def mock_journal(self, body):
        directory = self.root / "bin"
        directory.mkdir(exist_ok=True)
        command = directory / "journalctl"
        command.write_text(f"#!{sys.executable}\n" + body)
        command.chmod(0o755)
        return str(directory) + os.pathsep + os.environ["PATH"]

    def test_journal_process_limits_timeout_and_cli_default(self):
        path = self.mock_journal("import sys,json\nassert '--since=24 hours ago' in sys.argv\n"
                                 "print(json.dumps({'MESSAGE':'connection failed','PRIORITY':'3'}))\n")
        self.environment["PATH"] = path
        self.run_cli("scan", "--no-interactive")
        self.assertEqual(self.cache.load()["matches"], 1)
        path = self.mock_journal("import time\ntime.sleep(5)\n")
        with patch.dict(os.environ, PATH=path):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                journal_output(10, "today", timeout=0.1)
        path = self.mock_journal("print('x'*1024)\n")
        with patch.dict(os.environ, PATH=path), patch("log_scout_sources.MAX_BYTES", 100):
            with self.assertRaisesRegex(RuntimeError, "exceeds"):
                journal_output(10, "today")
        path = self.mock_journal("import sys\nprint('permission denied',file=sys.stderr)\nsys.exit(1)\n")
        with patch.dict(os.environ, PATH=path):
            with self.assertRaisesRegex(RuntimeError, "permission denied"):
                journal_output(10, "today")

    def test_cache_atomic_failure_schema_and_retention(self):
        data = self.sample()
        self.cache.save(data)
        with patch("LogScoutCache.os.replace", side_effect=OSError("publication failed")):
            with self.assertRaises(OSError):
                self.cache.save(self.sample())
        self.assertEqual(self.cache.load()["id"], data["id"])
        old = copy.deepcopy(data)
        then = datetime.now(timezone.utc) - timedelta(days=8)
        old["id"] = then.strftime("%Y%m%dT%H%M%S%fZ") + "-12345678"
        old["created_at"] = then.isoformat()
        self.cache.save(old)
        for _ in range(11):
            self.cache.save(self.sample())
        self.assertEqual(len(self.cache.history()), 10)
        self.assertFalse((self.cache.directory / (old["id"] + ".json")).exists())
        path = self.cache.directory / (self.cache.load()["id"] + ".json")
        data = json.loads(path.read_text())
        data["schema_version"] = 2
        path.write_text(json.dumps(data))
        self.run_cli("summary", expected=1)
        self.run_cli("purge-cache", "--yes", expected=1)
        self.assertEqual(len(list(self.cache.directory.glob("*.json"))), 10)

    def test_cache_paths_and_purge(self):
        self.run_cli("summary", expected=1)
        data = self.sample()
        self.cache.save(data)
        unrelated = self.cache.directory / "unrelated.txt"
        unrelated.write_text("keep")
        self.run_cli("purge-cache", "--yes")
        self.assertTrue(unrelated.exists())
        self.assertTrue(self.log.exists())
        self.environment["LOG_SCOUT_CACHE_DIR"] = "relative"
        self.run_cli("summary", expected=1)
        link = self.root / "cache-link"
        link.symlink_to(self.cache.directory, target_is_directory=True)
        self.environment["LOG_SCOUT_CACHE_DIR"] = str(link)
        self.run_cli("history", expected=1)
        self.environment["LOG_SCOUT_CACHE_DIR"] = str(self.cache.directory)
        self.cache.directory.chmod(0o755)
        self.run_cli("history", expected=1)

    def test_detail_cap_counts_all_findings(self):
        self.log.write_text("".join(f"ERROR unique-{chr(65 + i // 26)}{chr(65 + i % 26)}\n" for i in range(260)))
        data = self.sample()
        self.assertEqual(data["matches"], 260)
        self.assertEqual(len(data["groups"]), 250)
        self.assertEqual(data["omitted_matches"], 10)
        self.assertTrue(data["partial"])

    def test_empty_and_malformed_cached_data(self):
        self.log.write_text("")
        self.run_cli("scan", "--file", self.log)
        data = self.cache.load()
        self.assertEqual(data["matches"], 0)
        self.assertFalse(data["partial"])
        self.run_cli("details", "network")
        self.log.write_text("ERROR connection failed\n")
        self.run_cli("scan", "--file", self.log)
        path = self.cache.directory / (self.cache.load()["id"] + ".json")
        data = json.loads(path.read_text())
        data["groups"][0]["category"] = []
        path.write_text(json.dumps(data))
        self.run_cli("summary", expected=1)

    def test_concurrent_scans_keep_independent_snapshots(self):
        children = [subprocess.Popen([str(MODULE / "scripts/log-scout"), "scan", "--file", str(self.log)],
                                     env=self.environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    for _ in range(4)]
        for child in children:
            output, errors = child.communicate(timeout=15)
            self.assertEqual(child.returncode, 0, output + errors)
        self.assertEqual(len(self.cache.history()), 4)

    def test_system_scope_lifecycle(self):
        install_root = self.root / "system"
        self.environment["SHELL_SCRIPTS_INSTALL_ROOT"] = str(install_root)
        command = install_root / "usr/local/bin/log-scout"
        selections = [(REPOSITORY / "scripts/setup.sh", REPOSITORY / "scripts/uninstall.sh", ["--module", "log-scout"]),
                      (MODULE / "setup.sh", MODULE / "uninstall.sh", [])]
        for setup, uninstall, args in selections:
            subprocess.run([str(setup), "--system", *args], env=self.environment,
                           check=True, capture_output=True, cwd=self.root)
            self.run_cli("scan", "--file", self.log, executable=command)
            subprocess.run([str(uninstall), "--system", *args], env=self.environment,
                           check=True, capture_output=True, cwd=self.root)
            self.assertFalse(command.exists())

    def test_real_terminal_menu(self):
        master, slave = pty.openpty()
        child = subprocess.Popen([str(MODULE / "scripts/log-scout"), "scan", "--file", str(self.log)],
                                 env=self.environment, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        output = bytearray()
        steps = [(b"Category name/number", b"network\n"),
                 (b"Group number", b"1\n"),
                 (b"Representative examples", b"q\n")]
        deadline = time.monotonic() + 10
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(master, selectors.EVENT_READ)
                while time.monotonic() < deadline:
                    if selector.select(0.1):
                        try:
                            chunk = os.read(master, 8192)
                        except OSError:
                            break
                        if not chunk:
                            break
                        output.extend(chunk)
                        if steps and steps[0][0] in output:
                            _, answer = steps.pop(0)
                            os.write(master, answer)
                    if child.poll() is not None:
                        break
            self.assertFalse(steps, output.decode(errors="replace"))
            self.assertEqual(child.wait(timeout=2), 0)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
            os.close(master)
        self.assertIn(b"connection refused", output)

    def test_root_and_direct_lifecycle(self):
        command = self.root / "home/.local/bin/log-scout"
        for setup, uninstall in ((MODULE / "setup.sh", MODULE / "uninstall.sh"),
                                 (REPOSITORY / "scripts/setup.sh", REPOSITORY / "scripts/uninstall.sh")):
            for _ in range(2):
                args = ["--module", "log-scout"] if setup.parent == REPOSITORY / "scripts" else []
                subprocess.run([str(setup), *args], env=self.environment, check=True, capture_output=True)
            self.run_cli("scan", "--file", self.log, executable=command)
            original = command.read_bytes()
            command.write_bytes(original + b"# edited\n")
            result = subprocess.run([str(uninstall), *args], env=self.environment, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(command.exists())
            command.write_bytes(original)
            subprocess.run([str(uninstall), *args], env=self.environment, check=True, capture_output=True)
            self.assertFalse(command.exists())
            self.assertTrue(list(self.cache.directory.glob("*.json")))


if __name__ == "__main__":
    unittest.main()
