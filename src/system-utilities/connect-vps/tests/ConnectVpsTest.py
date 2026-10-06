#!/usr/bin/env python3
"""Exercise the private VPS registry and SSH command without a network connection."""

from __future__ import annotations

import io
import os
import runpy
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
REPOSITORY = MODULE.parents[2]
sys.path.insert(0, str(MODULE / "scripts"))

from Connection import Connection
from ConnectionStore import ConnectionStore, database_path
from ConnectVpsError import ConnectVpsError
from ssh_connection import connect


class ConnectVpsTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.data = self.root / "xdg-data"
        self.environment = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.data),
                                PYTHONDONTWRITEBYTECODE="1")
        self.path = self.data / "connect-vps/connections.sqlite3"
        self.script = MODULE / "scripts/connect-vps"
        self.cli = runpy.run_path(str(self.script), run_name="connect_vps_cli")["main"]

    def interactive(self, args: list[str], answers: list[str]) -> str:
        output = io.StringIO()
        with patch.dict(os.environ, self.environment), \
                patch("sys.stdin.isatty", return_value=True), \
                patch("builtins.input", side_effect=answers), redirect_stdout(output):
            self.assertEqual(self.cli(args), 0)
        return output.getvalue()

    def run_cli(self, *args: str, success: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run([sys.executable, str(self.script), *args],
                                env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def test_add_key_default_and_password_without_storing_secrets(self) -> None:
        self.interactive(["add"], ["production", "192.0.2.10", "deploy", "", "", ""])
        self.interactive(["add"], ["legacy", "2001:db8::1", "root", "2222", "p"])
        with patch.dict(os.environ, self.environment):
            with ConnectionStore() as store:
                records = {item.name: item for item in store.list()}
        self.assertEqual(records["production"].auth, "key")
        self.assertIsNone(records["production"].key_path)
        self.assertEqual(records["legacy"].auth, "password")
        self.assertEqual(records["legacy"].port, 2222)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        with sqlite3.connect(self.path) as database:
            columns = [row[1] for row in database.execute("PRAGMA table_info(connections)")]
        self.assertNotIn("password", columns)

    def test_update_delete_and_cancel(self) -> None:
        with patch.dict(os.environ, self.environment):
            with ConnectionStore() as store:
                store.add(Connection(None, "first", "192.0.2.1", "root", 22, "key"))
        self.assertIn("Updated 'renamed'", self.interactive(
            ["update"], ["1", "renamed", "", "deploy", "2200", "p"]))
        with patch.dict(os.environ, self.environment):
            with ConnectionStore() as store:
                item = store.list()[0]
                self.assertEqual((item.name, item.user, item.port, item.auth),
                                 ("renamed", "deploy", 2200, "password"))
        self.assertIn("Cancelled", self.interactive(["delete"], ["q"]))
        self.assertIn("Cancelled", self.interactive(["delete"], ["1", "n"]))
        self.assertIn("Deleted 'renamed'", self.interactive(["delete"], ["1", "yes"]))
        with patch.dict(os.environ, self.environment):
            with ConnectionStore() as store:
                self.assertEqual(store.list(), [])

    def test_default_command_selects_then_connects(self) -> None:
        with patch.dict(os.environ, self.environment):
            with ConnectionStore() as store:
                store.add(Connection(None, "selected", "192.0.2.4", "deploy", 22, "key"))
        with patch.dict(self.cli.__globals__, connect=lambda item: 0 if item.name == "selected" else 1):
            self.assertIn("Saved VPS connections", self.interactive([], ["wrong", "1"]))
        with patch.dict(self.cli.__globals__, connect=lambda _: self.fail("SSH should not start")):
            self.assertIn("Cancelled", self.interactive([], ["q"]))

    def test_explicit_private_key_and_public_key_rejection(self) -> None:
        private_key = self.root / "id_example"
        private_key.write_text("fake private key")
        output = self.interactive(["add"], ["keyed", "192.0.2.8", "root", "", "", "id_example.pub",
                                            str(private_key)])
        self.assertIn("Select the private key file", output)
        with patch.dict(os.environ, self.environment):
            with ConnectionStore() as store:
                self.assertEqual(store.list()[0].key_path, str(private_key))

    def test_key_path_and_ssh_authentication_modes(self) -> None:
        private_key = self.root / "id_test"
        private_key.write_text("fake private key")
        with patch("ssh_connection.shutil.which", return_value="/usr/bin/ssh"), \
                patch("ssh_connection.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(connect(Connection(None, "key", "192.0.2.1", "root", 22,
                                                "key", str(private_key))), 0)
            command = run.call_args.args[0]
            self.assertEqual(command[-2:], ["--", "192.0.2.1"])
            self.assertIn(str(private_key), command)
            self.assertIn("PasswordAuthentication=no", command)
            self.assertIn("IdentitiesOnly=yes", command)
            self.assertIn("BatchMode=no", command)
            self.assertEqual(connect(Connection(None, "default", "192.0.2.2", "root", 22,
                                                "key")), 0)
            self.assertNotIn("-i", run.call_args.args[0])
            self.assertEqual(connect(Connection(None, "password", "2001:db8::1", "root", 2200,
                                                "password")), 0)
            command = run.call_args.args[0]
            self.assertEqual(command[-2:], ["--", "2001:db8::1"])
            self.assertIn("PubkeyAuthentication=no", command)
            self.assertNotIn("-i", command)
        private_key.unlink()
        with patch("ssh_connection.shutil.which", return_value="/usr/bin/ssh"):
            with self.assertRaisesRegex(ConnectVpsError, "private key not found"):
                connect(Connection(None, "key", "192.0.2.1", "root", 22, "key", str(private_key)))

    def test_invalid_input_symlinks_and_noninteractive_calls(self) -> None:
        self.assertIn("requires an interactive terminal", self.run_cli("add", success=False).stderr)
        self.assertIn("requires an interactive terminal", self.run_cli(success=False).stderr)
        self.assertNotEqual(self.run_cli("add", "extra", success=False).returncode, 0)
        self.assertIn("no saved VPS connections", self._empty_picker_error())
        with patch.dict(os.environ, XDG_DATA_HOME="relative"):
            with self.assertRaisesRegex(ConnectVpsError, "absolute"):
                database_path()
        target = self.root / "target.sqlite3"
        target.write_bytes(b"unchanged")
        self.path.unlink()
        self.path.symlink_to(target)
        with patch.dict(os.environ, self.environment):
            with self.assertRaisesRegex(ConnectVpsError, "symbolic-link database"):
                with ConnectionStore():
                    pass
        self.assertEqual(target.read_bytes(), b"unchanged")

    def _empty_picker_error(self) -> str:
        with patch.dict(os.environ, self.environment), patch("sys.stdin.isatty", return_value=True):
            with self.assertRaisesRegex(ConnectVpsError, "no saved VPS connections") as error:
                self.cli([])
        return str(error.exception)

    def test_install_from_another_directory_and_preserve_registry(self) -> None:
        result = subprocess.run([str(REPOSITORY / "scripts/setup.sh"), "--module", "connect-vps"],
                                cwd=REPOSITORY, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.home / ".local/bin/connect-vps"
        self.assertTrue(installed.is_file())
        result = subprocess.run([str(installed), "--help"], cwd=self.root, env=self.environment,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with patch.dict(os.environ, self.environment):
            with ConnectionStore() as store:
                store.add(Connection(None, "kept", "192.0.2.1", "root", 22, "key"))
        result = subprocess.run([str(REPOSITORY / "scripts/uninstall.sh"), "--module", "connect-vps"],
                                cwd=REPOSITORY, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(installed.exists())
        with patch.dict(os.environ, self.environment):
            with ConnectionStore() as store:
                self.assertEqual(store.list()[0].name, "kept")

    def test_system_scope_installs_command_for_all_users(self) -> None:
        install_root = self.root / "system-root"
        environment = dict(self.environment, SHELL_SCRIPTS_INSTALL_ROOT=str(install_root))
        result = subprocess.run([str(REPOSITORY / "scripts/setup.sh"), "--system", "--module", "connect-vps"],
                                cwd=REPOSITORY, env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = install_root / "usr/local/bin/connect-vps"
        self.assertTrue(installed.is_file())
        result = subprocess.run([str(installed), "--help"], cwd=self.root, env=environment,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(REPOSITORY / "scripts/uninstall.sh"), "--system", "--module", "connect-vps"],
                                cwd=REPOSITORY, env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(installed.exists())


if __name__ == "__main__":
    unittest.main()
