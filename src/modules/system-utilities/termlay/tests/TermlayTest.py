#!/usr/bin/env python3
"""Exercise Termlay's interactive CLI, capture, storage, and installation."""

from __future__ import annotations

import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
REPOSITORY = MODULE.parents[3]
sys.path[:0] = [str(MODULE / "scripts" / concern) for concern in ("layout", "ptyxis")]
sys.path.insert(0, str(MODULE / "scripts"))

from Layout import Layout
from LayoutStore import LayoutStore
from TermlayError import TermlayError
from current_layout import current_layout, directory_from_title
from layout_paths import config_directory
from process_directory import foreground_directory


class TermlayTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
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
        self.store = LayoutStore(self.xdg / "termlay/layouts")
        self.cli = runpy.run_path(str(self.command), run_name="termlay_cli")["main"]

    def run_cli(self, *args: str, success: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run([sys.executable, str(self.command), *args], cwd=self.first,
                                env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def interactive(self, command: str, answers: list[str], titles: list[str] | None = None) -> str:
        output = io.StringIO()
        with patch.dict(os.environ, self.environment), \
                patch("sys.stdin.isatty", return_value=True), \
                patch.dict(self.cli.__globals__, read_current_tab_titles=lambda: titles or []), \
                patch("builtins.input", side_effect=answers), redirect_stdout(output):
            self.assertEqual(self.cli([command]), 0)
        return output.getvalue()

    def test_commands_and_interactive_requirement(self) -> None:
        help_text = self.run_cli("--help").stdout
        self.assertIn("{save,update,delete,list,ls}", help_text)
        self.assertIn("termlay 0.4.0", self.run_cli("--version").stdout)
        for old in ("open", "show", "save-current", "s", "rm"):
            self.assertIn("unknown command", self.run_cli(old, success=False).stderr)
        for command in ("save", "update", "delete"):
            self.assertIn("requires an interactive terminal", self.run_cli(command, success=False).stderr)
        self.assertIn("unknown command 'xyz'", self.run_cli("xyz", success=False).stderr)

    def test_list_and_ls_print_sorted_names_without_interaction(self) -> None:
        self.assertEqual(self.run_cli("list").stdout, "")
        for name in ("zeta", "alpha", "middle"):
            self.store.save(Layout(name, (self.first,)))
        expected = "alpha\nmiddle\nzeta\n"
        self.assertEqual(self.run_cli("list").stdout, expected)
        self.assertEqual(self.run_cli("ls").stdout, expected)

    def test_save_selects_tabs_in_window_order_and_keeps_private_storage(self) -> None:
        titles = [f"user@host: {self.first}", f"user@host: {self.second}",
                  f"user@host: {self.first}"]
        output = self.interactive("save", ["3,1,3", "work"], titles)
        self.assertIn("Saved layout 'work' (2 tabs)", output)
        path = self.store.path("work")
        self.assertEqual(json.loads(path.read_text())["tabs"],
                         [{"cwd": str(self.first)}, {"cwd": str(self.first)}])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        with self.assertRaisesRegex(TermlayError, "already exists"):
            self.interactive("save", ["all", "work"], titles)
        self.assertEqual(self.store.load("work").directories, (self.first, self.first))

    def test_save_cancel_invalid_selection_and_manual_fallback(self) -> None:
        titles = ["Unknown tab", f"user@host: {self.second}"]
        self.assertIn("Save cancelled", self.interactive("save", ["q"], titles))
        self.assertIn("Save cancelled", self.interactive("save", ["all", ""], titles))
        output = self.interactive("save", ["0", "3", "2,1", "manual", str(self.first)], titles)
        self.assertIn("Enter listed numbers", output)
        self.assertEqual(self.store.load("manual").directories, (self.first, self.second))
        with self.assertRaisesRegex(TermlayError, "layout name"):
            self.interactive("save", ["all", "../bad"], titles)
        with self.assertRaisesRegex(TermlayError, "no Ptyxis tabs"):
            self.interactive("save", [], [])

    def test_update_selects_layouts_and_tabs_with_confirmation(self) -> None:
        self.store.save(Layout("alpha", (self.first,)))
        self.store.save(Layout("beta", (self.first,)))
        titles = [f"user@host: {self.first}", f"user@host: {self.second}"]
        original = self.store.path("alpha").read_bytes()
        self.assertIn("Update cancelled", self.interactive("update", ["all", "1", "2", "n"], titles))
        self.assertEqual(self.store.path("alpha").read_bytes(), original)
        self.assertIn("Updated layout 'beta'", self.interactive("update", ["2", "2", "yes"], titles))
        self.assertEqual(self.store.load("beta").directories, (self.second,))
        self.assertEqual(self.store.load("alpha").directories, (self.first,))
        self.assertIn("Update cancelled", self.interactive("update", ["q"], titles))

    def test_delete_selects_and_confirms(self) -> None:
        for name in ("alpha", "beta", "gamma"):
            self.store.save(Layout(name, (self.first,)))
        self.assertIn("Delete cancelled", self.interactive("delete", ["all", "n"]))
        self.assertEqual(self.store.list_names(), ["alpha", "beta", "gamma"])
        self.assertIn("Deleted layout 'beta'", self.interactive("delete", ["2", "y"]))
        self.assertEqual(self.store.list_names(), ["alpha", "gamma"])
        self.assertIn("Delete cancelled", self.interactive("delete", ["q"]))
        self.interactive("delete", ["all", "yes"])
        self.assertEqual(self.store.list_names(), [])
        with self.assertRaisesRegex(TermlayError, "no saved layouts"):
            self.interactive("delete", [EOFError()])

    def test_capture_errors_do_not_change_layout(self) -> None:
        self.store.save(Layout("work", (self.first,)))
        original = self.store.path("work").read_bytes()
        with self.assertRaisesRegex(TermlayError, "not provided"):
            self.interactive("update", ["1", "all", ""], ["Unknown tab"])
        self.assertEqual(self.store.path("work").read_bytes(), original)
        with self.assertRaisesRegex(TermlayError, "selection cancelled"):
            self.interactive("delete", [EOFError()])

    def test_storage_path_validation_and_symlink_refusal(self) -> None:
        with patch.dict(os.environ, self.environment):
            self.assertEqual(config_directory(), self.store.directory)
        with patch.dict(os.environ, {"HOME": str(self.home)}, clear=True):
            self.assertEqual(config_directory(), self.home / ".config/termlay/layouts")
        with patch.dict(os.environ, XDG_CONFIG_HOME="relative"):
            with self.assertRaisesRegex(TermlayError, "absolute"):
                config_directory()
        with self.assertRaisesRegex(TermlayError, "layout name"):
            self.store.path("../escape")
        self.store.save(Layout("work", (self.first,)))
        path = self.store.path("work")
        path.unlink()
        path.symlink_to(self.root / "target")
        for action in (lambda: self.store.load("work"),
                       lambda: self.store.replace(Layout("work", (self.second,))),
                       lambda: self.store.delete("work")):
            with self.assertRaisesRegex(TermlayError, "symbolic-link"):
                action()

    def test_title_resolution_and_manual_directory(self) -> None:
        self.assertEqual(directory_from_title("user@host: ~/project"), "~/project")
        self.assertIsNone(directory_from_title("Editor — node /usr/bin/codex"))
        with patch("current_layout.read_current_tab_titles", return_value=["Unknown tab"]), \
                patch("builtins.input", return_value=str(self.second)):
            self.assertEqual(current_layout("manual").directories, (self.second,))
        self.assertIsNone(foreground_directory("unmatched command", self.root))

    def test_identical_foreground_commands_use_workspace_label(self) -> None:
        proc = self.root / "proc"
        proc.mkdir()
        projects = [self.root / "Linux-Utilities", self.root / "Finance-Planner"]
        for project in projects:
            project.mkdir()
        for pid, parent, comm, argv, cwd in (
            (100, 1, "ptyxis-agent", b"ptyxis-agent", self.root),
            (101, 100, "bash", b"bash", projects[0]),
            (102, 101, "node", b"node\0/home/lars/.local/bin/codex\0", projects[0]),
            (103, 100, "bash", b"bash", projects[1]),
            (104, 103, "node", b"node\0/home/lars/.local/bin/codex\0", projects[1]),
        ):
            process = proc / str(pid)
            process.mkdir()
            (process / "comm").write_text(comm)
            (process / "status").write_text(f"PPid:\t{parent}\n")
            (process / "cmdline").write_bytes(argv)
            (process / "cwd").symlink_to(cwd, target_is_directory=True)
        for project in projects:
            title = f"Analyze this project | {project.name} — node /home/lars/.local/bin/codex"
            self.assertEqual(foreground_directory(title, proc), str(project))
        self.assertIsNone(foreground_directory("Other — node /home/lars/.local/bin/codex", proc))

    def test_installed_command_from_another_directory(self) -> None:
        result = subprocess.run([str(REPOSITORY / "setup.sh"), "--module", "termlay"],
                                cwd=REPOSITORY, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.home / ".local/bin/termlay"
        self.assertTrue(installed.is_file())
        result = subprocess.run([str(installed), "--help"], cwd=self.second,
                                env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("{save,update,delete,list,ls}", result.stdout)
        self.store.save(Layout("preserved", (self.first,)))
        result = subprocess.run([str(REPOSITORY / "uninstall.sh"), "--module", "termlay"],
                                cwd=REPOSITORY, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(installed.exists())
        self.assertEqual(self.store.load("preserved").directories, (self.first,))


if __name__ == "__main__":
    unittest.main()
