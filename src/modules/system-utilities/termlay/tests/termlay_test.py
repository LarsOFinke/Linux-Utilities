#!/usr/bin/env python3
"""Exercise termlay storage, CLI, and Ptyxis arguments without a display."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
REPOSITORY = MODULE.parents[3]
sys.path.insert(0, str(MODULE / "scripts"))

from termlay_core import Layout, LayoutStore, TermlayError, config_directory, layout_from_paths, missing_directories
from termlay_ptyxis import PtyxisBackend


class TermlayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.first = self.root / "first"
        self.second = self.root / "second"
        self.first.mkdir()
        self.second.mkdir()
        self.xdg = self.root / "xdg"
        self.environment = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.xdg),
                                PYTHONDONTWRITEBYTECODE="1")
        self.command = MODULE / "scripts/termlay"

    def run_cli(self, *args: str, success: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run([sys.executable, str(self.command), *args], cwd=self.first,
                                env=env or self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def test_save_load_order_json_and_show(self) -> None:
        self.run_cli("save", "work", str(self.second), ".", str(self.second))
        path = self.xdg / "termlay/layouts/work.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data, {"version": 1, "name": "work", "tabs": [
            {"cwd": str(self.second)}, {"cwd": str(self.first)}, {"cwd": str(self.second)}]})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(LayoutStore(path.parent).load("work").directories,
                         (self.second, self.first, self.second))
        self.assertEqual(self.run_cli("show", "work").stdout,
                         f"Layout: work\n\n1  {self.second}\n2  {self.first}\n3  {self.second}\n")

    def test_duplicate_force_list_aliases_and_delete(self) -> None:
        self.run_cli("s", "zeta", str(self.first))
        duplicate = self.run_cli("save", "zeta", str(self.second), success=False)
        self.assertIn("use --force", duplicate.stderr)
        self.assertEqual(self.run_cli("show", "zeta").stdout.count(str(self.first)), 1)
        self.run_cli("save", "zeta", str(self.second), "--force")
        self.run_cli("save", "alpha", str(self.first))
        self.assertEqual(self.run_cli("ls").stdout, "alpha\nzeta\n")
        self.assertIn(str(self.second), self.run_cli("show", "zeta").stdout)
        self.run_cli("rm", "zeta")
        self.assertEqual(self.run_cli("list").stdout, "alpha\n")
        self.assertIn("not found", self.run_cli("delete", "zeta", success=False).stderr)

    def test_nonexistent_invalid_names_and_directories(self) -> None:
        self.assertIn("not found", self.run_cli("open", "missing", success=False).stderr)
        self.assertIn("not found", self.run_cli("show", "missing", success=False).stderr)
        self.assertIn("at least one", self.run_cli("save", "empty", success=False).stderr)
        self.assertIn("not an existing directory", self.run_cli(
            "save", "bad", str(self.root / "absent"), success=False).stderr)
        self.assertIn("layout name", self.run_cli("save", "../escape", str(self.first), success=False).stderr)
        self.assertEqual(self.run_cli("list").stdout, "")

    def test_xdg_and_home_fallback(self) -> None:
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.xdg), "HOME": str(self.home)}):
            self.assertEqual(config_directory(), self.xdg / "termlay/layouts")
        with patch.dict(os.environ, {"HOME": str(self.home)}, clear=True):
            self.assertEqual(config_directory(), self.home / ".config/termlay/layouts")
        fallback = dict(self.environment)
        del fallback["XDG_CONFIG_HOME"]
        self.run_cli("save", "home", str(self.first), env=fallback)
        self.assertTrue((self.home / ".config/termlay/layouts/home.json").is_file())
        relative = dict(self.environment, XDG_CONFIG_HOME="relative")
        self.assertIn("absolute", self.run_cli("list", success=False, env=relative).stderr)

    def test_home_expansion_and_canonical_paths(self) -> None:
        project = self.home / "project"
        project.mkdir()
        shortcut = self.root / "shortcut"
        shortcut.symlink_to(project, target_is_directory=True)
        self.run_cli("save", "home", "~/project", str(shortcut))
        data = json.loads((self.xdg / "termlay/layouts/home.json").read_text(encoding="utf-8"))
        self.assertEqual(data["tabs"], [{"cwd": str(project)}, {"cwd": str(project)}])

    def test_serialization_errors_and_symlink_refusal(self) -> None:
        store = LayoutStore(self.xdg / "termlay/layouts")
        store.directory.mkdir(parents=True)
        path = store.path("broken")
        path.write_text("not json", encoding="utf-8")
        with self.assertRaises(TermlayError):
            store.load("broken")
        path.write_text(json.dumps({"version": 2, "name": "broken", "tabs": []}), encoding="utf-8")
        with self.assertRaises(TermlayError):
            store.load("broken")
        path.unlink()
        path.symlink_to(self.root / "target")
        with self.assertRaises(TermlayError):
            store.save(Layout("broken", (self.first,)), force=True)
        with self.assertRaises(TermlayError):
            store.load("broken")

    def test_open_validates_all_before_ptyxis_and_preserves_order(self) -> None:
        self.run_cli("save", "work", str(self.first), str(self.second))
        mock_bin = self.root / "bin"
        mock_bin.mkdir()
        log = self.root / "ptyxis-args.jsonl"
        fake = mock_bin / "ptyxis"
        fake.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                        "with open(os.environ['PTYXIS_TEST_LOG'], 'a', encoding='utf-8') as stream:\n"
                        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n", encoding="utf-8")
        fake.chmod(0o755)
        environment = dict(self.environment, PATH=f"{mock_bin}:{os.environ['PATH']}", PTYXIS_TEST_LOG=str(log))
        self.assertIn("Opening layout 'work' (2 tabs)", self.run_cli("o", "work", env=environment).stdout)
        self.assertEqual([json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()],
                         [["--tab", "--working-directory", str(self.first)],
                          ["--tab", "--working-directory", str(self.second)]])
        log.unlink()
        self.second.rmdir()
        failed = self.run_cli("open", "work", success=False, env=environment)
        self.assertIn(str(self.second), failed.stderr)
        self.assertFalse(log.exists())

    def test_backend_is_mockable(self) -> None:
        layout = layout_from_paths("work", [str(self.first), str(self.second)])
        self.assertEqual(missing_directories(layout), [])
        with patch("termlay_ptyxis.shutil.which", return_value="/usr/bin/ptyxis"), \
                patch("termlay_ptyxis.subprocess.run") as run:
            PtyxisBackend().open_layout(layout)
        self.assertEqual([call.args[0][-1] for call in run.call_args_list],
                         [str(self.first), str(self.second)])

    def test_help_version_and_unknown_command(self) -> None:
        self.assertIn("save", self.run_cli("--help").stdout)
        self.assertIn("termlay 0.1.0", self.run_cli("--version").stdout)
        result = self.run_cli("xyz", success=False)
        self.assertIn("unknown command 'xyz'", result.stderr)
        self.assertIn("termlay --help", result.stderr)

    def test_installed_command_from_another_directory(self) -> None:
        result = subprocess.run([str(REPOSITORY / "setup.sh"), "--module", "termlay"],
                                cwd=REPOSITORY, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.home / ".local/bin/termlay"
        self.assertTrue(installed.is_file())
        result = subprocess.run([str(installed), "save", "installed", str(self.first)],
                                cwd=self.second, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.xdg / "termlay/layouts/installed.json").is_file())
        result = subprocess.run([str(REPOSITORY / "uninstall.sh"), "--module", "termlay"],
                                cwd=REPOSITORY, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(installed.exists())
        self.assertTrue((self.xdg / "termlay/layouts/installed.json").is_file())


if __name__ == "__main__":
    unittest.main()
