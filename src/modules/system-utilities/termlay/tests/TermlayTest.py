#!/usr/bin/env python3
"""Exercise termlay storage, CLI, and Ptyxis arguments without a display."""

from __future__ import annotations

import hashlib
import fcntl
import io
import json
import os
import pty
import runpy
import subprocess
import sys
import tempfile
import termios
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
from PtyxisBackend import PtyxisBackend
from TermlayError import TermlayError
from current_layout import current_layout, directory_from_title
from layout_paths import config_directory, layout_from_paths, missing_directories
from process_directory import foreground_directory


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

    def test_duplicate_save_requires_update_to_replace_layout(self) -> None:
        self.run_cli("s", "zeta", str(self.first))
        duplicate = self.run_cli("save", "zeta", str(self.second), success=False)
        self.assertIn("termlay update", duplicate.stderr)
        self.assertEqual(self.run_cli("show", "zeta").stdout.count(str(self.first)), 1)
        self.run_cli("delete", "zeta")
        self.run_cli("save", "zeta", str(self.second))
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
            store.replace(Layout("broken", (self.first,)))
        with self.assertRaises(TermlayError):
            store.load("broken")

    def test_symlinked_layout_directory_is_refused_without_touching_target(self) -> None:
        target = self.root / "shared"
        target.mkdir(mode=0o755)
        target.chmod(0o755)
        sentinel = target / "work.json"
        sentinel.write_text("leave me alone", encoding="utf-8")
        layout_directory = self.xdg / "termlay/layouts"
        layout_directory.parent.mkdir(parents=True)
        layout_directory.symlink_to(target, target_is_directory=True)

        for args in (("save", "work", str(self.first)), ("list",),
                     ("show", "work"), ("delete", "work")):
            result = self.run_cli(*args, success=False)
            self.assertIn("symbolic-link layout directory", result.stderr)
        self.assertEqual(target.stat().st_mode & 0o777, 0o755)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "leave me alone")

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
        with patch("PtyxisBackend.shutil.which", return_value="/usr/bin/ptyxis"), \
                patch.object(PtyxisBackend, "current_shell", return_value=None), \
                patch("PtyxisBackend.subprocess.run") as run:
            PtyxisBackend().open_layout(layout)
        self.assertEqual([call.args[0][-1] for call in run.call_args_list],
                         [str(self.first), str(self.second)])

    def test_interactive_open_reuses_origin_tab(self) -> None:
        mock_bin = self.root / "bin"
        mock_bin.mkdir()
        log = self.root / "opened.jsonl"
        for name in ("ptyxis", "test-shell"):
            executable = mock_bin / name
            executable.write_text(
                f"#!{sys.executable}\nimport json, os, sys\n"
                "with open(os.environ['TERMLAY_TEST_LOG'], 'a') as stream:\n"
                f"    stream.write(json.dumps([{name!r}, sys.argv[1:], os.getcwd(), os.environ.get('PWD')]) + '\\n')\n")
            executable.chmod(0o755)
        environment = dict(self.environment, PTYXIS_VERSION="test", SHELL=str(mock_bin / "test-shell"),
                           PATH=f"{mock_bin}:{os.environ['PATH']}", TERMLAY_TEST_LOG=str(log))
        for variable in ("TMUX", "STY", "SSH_CONNECTION"):
            environment.pop(variable, None)

        def own_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        def open_interactively(*args):
            master, slave = pty.openpty()
            try:
                with subprocess.Popen([sys.executable, str(self.command), "open", "work", *args],
                                      stdin=slave, stdout=slave, stderr=slave, cwd=self.first,
                                      env=environment, preexec_fn=own_terminal) as child:
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                        self.fail("interactive open did not finish")
                    self.assertEqual(child.returncode, 0)
            finally:
                os.close(slave)
                os.close(master)
            records = [json.loads(line) for line in log.read_text().splitlines()]
            log.unlink()
            return records

        # A one-tab layout starts its shell in place, without invoking Ptyxis.
        self.run_cli("save", "work", str(self.second))
        self.assertEqual(open_interactively(), [
            ["test-shell", ["-i"], str(self.second), str(self.second)]])
        self.run_cli("delete", "work")
        self.run_cli("save", "work", str(self.first), str(self.second))
        records = open_interactively()
        self.assertEqual([record[:2] for record in records], [
            ["ptyxis", ["--tab", "--working-directory", str(self.second)]],
            ["test-shell", ["-i"]]])
        self.assertEqual(records[-1][2:], [str(self.first), str(self.first)])
        records = open_interactively("--new-tabs")
        self.assertEqual([record[:2] for record in records], [
            ["ptyxis", ["--tab", "--working-directory", str(self.first)]],
            ["ptyxis", ["--tab", "--working-directory", str(self.second)]]])

    def test_failed_tab_creation_does_not_replace_current_shell(self) -> None:
        layout = layout_from_paths("work", [str(self.first), str(self.second)])
        with patch("PtyxisBackend.shutil.which", return_value="/usr/bin/ptyxis"), \
                patch.object(PtyxisBackend, "current_shell", return_value="/bin/bash"), \
                patch("PtyxisBackend.subprocess.run", side_effect=subprocess.CalledProcessError(1, "ptyxis")), \
                patch("PtyxisBackend.os.execvpe") as execute, patch("PtyxisBackend.os.chdir") as chdir:
            with self.assertRaisesRegex(TermlayError, "Ptyxis failed"):
                PtyxisBackend().open_layout(layout)
            execute.assert_not_called()
            chdir.assert_not_called()

    def test_current_shell_requires_foreground_ptyxis_terminal(self) -> None:
        with patch.dict(os.environ, {"PTYXIS_VERSION": "test", "SHELL": "/bin/sh"}, clear=True), \
                patch("PtyxisBackend.sys.stdin.isatty", return_value=True), \
                patch("PtyxisBackend.sys.stdout.isatty", return_value=True), \
                patch("PtyxisBackend.sys.stdin.fileno", return_value=0), \
                patch("PtyxisBackend.os.tcgetpgrp", return_value=os.getpgrp()):
            self.assertIsNotNone(PtyxisBackend().current_shell())
            for variable in ("TMUX", "STY", "SSH_CONNECTION"):
                with patch.dict(os.environ, {variable: "active"}):
                    self.assertIsNone(PtyxisBackend().current_shell())
            with patch.dict(os.environ, PTYXIS_VERSION=""):
                self.assertIsNone(PtyxisBackend().current_shell())
            with patch("PtyxisBackend.os.tcgetpgrp", return_value=-1):
                self.assertIsNone(PtyxisBackend().current_shell())
            with patch("PtyxisBackend.sys.stdin.isatty", return_value=False):
                self.assertIsNone(PtyxisBackend().current_shell())
            with patch.dict(os.environ, SHELL="/nonexistent/termlay-test-shell"):
                with self.assertRaisesRegex(TermlayError, "shell is not executable"):
                    PtyxisBackend().current_shell()

    def test_current_titles_foreground_process_and_manual_fallback(self) -> None:
        self.assertEqual(directory_from_title("lars@laptop: ~/project"), "~/project")
        self.assertIsNone(directory_from_title("Editor — node /usr/bin/codex"))

        proc = self.root / "proc"
        proc.mkdir()
        for pid, parent, comm, argv in (("100", "1", "ptyxis-agent", b"ptyxis-agent\0"),
                                         ("101", "100", "bash", b"bash\0"),
                                         ("102", "101", "node", b"node\0/usr/bin/codex\0")):
            process = proc / pid
            process.mkdir()
            (process / "comm").write_text(comm + "\n", encoding="utf-8")
            (process / "status").write_text(f"PPid:\t{parent}\n", encoding="utf-8")
            (process / "cmdline").write_bytes(argv)
        (proc / "101/cwd").symlink_to(self.second, target_is_directory=True)
        title = "Editor — node /usr/bin/codex"
        self.assertEqual(foreground_directory(title, proc), str(self.second))
        duplicate = proc / "103"
        duplicate.mkdir()
        (duplicate / "cmdline").write_bytes(b"node\0/usr/bin/codex\0")
        self.assertEqual(foreground_directory(title, proc), str(self.second))
        other = proc / "104"
        other.mkdir()
        (other / "comm").write_text("python\n", encoding="utf-8")
        (other / "status").write_text("PPid:\t101\n", encoding="utf-8")
        (other / "cmdline").write_bytes(b"python\0/tmp/app.py\0")
        self.assertEqual(foreground_directory("Editor — python /tmp/app.py", proc), str(self.second))

        fallback_proc = self.root / "fallback-proc"
        fallback_proc.mkdir()
        project = self.root / "Portfolio"
        project.mkdir()
        for pid, parent, comm, argv in (
            ("200", "1", "ptyxis-agent", b"ptyxis-agent\0"),
            ("201", "200", "bash", b"bash\0"),
            ("202", "201", "node", b"node\0/opt/codex/codex.js\0"),
        ):
            process = fallback_proc / pid
            process.mkdir()
            (process / "comm").write_text(comm + "\n", encoding="utf-8")
            (process / "status").write_text(f"PPid:\t{parent}\n", encoding="utf-8")
            (process / "cmdline").write_bytes(argv)
        (fallback_proc / "201/cwd").symlink_to(project, target_is_directory=True)
        title_with_launcher = "Portfolio — node /home/lars/.local/bin/codex "
        self.assertIsNone(foreground_directory(title_with_launcher, fallback_proc))

        with patch("current_layout.read_current_tab_titles", return_value=[
            f"lars@laptop: {self.first}", title,
            f"lars@laptop: {self.root / 'missing'}", "Unknown tab"]), \
                patch("current_layout.foreground_directory",
                      side_effect=lambda value: str(self.second) if value == title else None), \
                patch("builtins.input", side_effect=[str(self.first), str(self.first)]):
            layout = current_layout("captured")
        self.assertEqual(layout.directories, (self.first, self.second, self.first, self.first))

    def test_same_launcher_in_multiple_workspaces(self) -> None:
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
            title = f"⠸ Analyze this project | {project.name} — node /home/lars/.local/bin/codex "
            self.assertEqual(foreground_directory(title, proc), str(project))
        self.assertIsNone(foreground_directory("Portfolio — node /home/lars/.local/bin/codex ", proc))
        self.assertIsNone(foreground_directory("Linux-Utilities — node /other/program.js", proc))
        self.assertEqual(directory_from_title(
            "lars@laptop: ~/Projekte/Portfolio — python3 /home/lars/.local/bin/termlay update "),
            "~/Projekte/Portfolio")

    def test_save_current_cancel_preserves_existing_layout(self) -> None:
        self.run_cli("save", "work", str(self.first))
        existing = self.xdg / "termlay/layouts/work.json"
        original = existing.read_bytes()
        cli = runpy.run_path(str(self.command), run_name="termlay_cli")["main"]
        with patch.dict(os.environ, self.environment), \
                patch("current_layout.read_current_tab_titles", return_value=["Unknown tab"]), \
                patch("builtins.input", return_value=""):
            with self.assertRaises(TermlayError):
                cli(["save-current", "work"])
        with patch("current_layout.read_current_tab_titles", return_value=[]):
            with self.assertRaisesRegex(TermlayError, "no Ptyxis tabs"):
                cli(["save-current", "work"])
        self.assertEqual(existing.read_bytes(), original)

    def test_save_current_cli_writes_discovered_tabs_in_order(self) -> None:
        cli = runpy.run_path(str(self.command), run_name="termlay_cli")["main"]
        with patch.dict(os.environ, self.environment), \
                patch("current_layout.read_current_tab_titles", return_value=[
                    f"lars@laptop: {self.second}", f"lars@laptop: {self.first}"]), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(cli(["save-current", "captured"]), 0)
        saved = LayoutStore(self.xdg / "termlay/layouts").load("captured")
        self.assertEqual(saved.directories, (self.second, self.first))

    def test_help_version_and_unknown_command(self) -> None:
        self.assertIn("save", self.run_cli("--help").stdout)
        self.assertIn("termlay 0.2.0", self.run_cli("--version").stdout)
        result = self.run_cli("xyz", success=False)
        self.assertIn("unknown command 'xyz'", result.stderr)
        self.assertIn("termlay --help", result.stderr)

    def test_installed_command_from_another_directory(self) -> None:
        result = subprocess.run([str(REPOSITORY / "setup.sh"), "--module", "termlay"],
                                cwd=REPOSITORY, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.home / ".local/bin/termlay"
        self.assertTrue(installed.is_file())
        registry_path = self.home / ".local/state/shell-scripts/registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        for name in ("termlay_core.py", "termlay_ptyxis.py"):
            legacy = installed.parent / name
            legacy.write_text("old helper\n", encoding="utf-8")
            registry["modules"]["termlay"]["commands"][name] = {
                "path": str(legacy), "source": str(legacy),
                "sha256": hashlib.sha256(legacy.read_bytes()).hexdigest()}
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        result = subprocess.run([str(REPOSITORY / "setup.sh"), "--module", "termlay"],
                                cwd=REPOSITORY, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((installed.parent / "termlay_core.py").exists())
        self.assertFalse((installed.parent / "termlay_ptyxis.py").exists())
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
