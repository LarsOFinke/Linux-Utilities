#!/usr/bin/env python3
"""Persistent menu behavior without running an installer or touching host state."""
import importlib.util
import json
import os
import pty
import tempfile
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("utility_menu", ROOT / "installer/menu.py")
menu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(menu)


class MenuTests(unittest.TestCase):
    def test_success_failure_and_back_return_to_menu(self):
        with patch.object(menu.sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", side_effect=["wrong", "4", "1", "1", "1", "0"]), \
                patch.object(menu.subprocess, "run", side_effect=[subprocess.CompletedProcess([], code)
                                                                  for code in (0, 1, 3, 0)]) as run:
            self.assertEqual(menu.main(), 0)
        self.assertEqual(run.call_count, 4)
        self.assertEqual(run.call_args_list[0].args[0][-1], "--list")

    def test_real_install_returns_to_menu_and_browse_then_exit(self):
        catalog = json.loads((ROOT / "configuration/install.json").read_text())["modules"]
        modules = sorted(name for name, path in catalog.items()
                         if json.loads((ROOT / path).read_text())["category"] == "System utilities")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            master, slave = pty.openpty()
            process = None
            try:
                process = subprocess.Popen([str(ROOT / "main.sh")], stdin=slave,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           env=dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1"))
                os.close(slave)
                slave = -1
                os.write(master, f"1\n4\n{modules.index('loc-rank') + 1}\n4\nq\n".encode())
                output, unused = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, output.decode())
                self.assertEqual(output.count(b"Linux-Utilities\n"), 3)
                registry = json.loads((home / ".local/state/shell-scripts/registry.json").read_text())
                self.assertEqual(set(registry["modules"]), {"loc-rank"})
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
                if slave >= 0:
                    os.close(slave)
                os.close(master)

    def test_eof_and_interrupt_exit_without_changes(self):
        for interruption in (EOFError, KeyboardInterrupt):
            with patch.object(menu.sys.stdin, "isatty", return_value=True), \
                    patch("builtins.input", side_effect=interruption), \
                    patch.object(menu.subprocess, "run") as run:
                self.assertEqual(menu.main(), 0)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
