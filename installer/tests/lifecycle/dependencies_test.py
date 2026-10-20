#!/usr/bin/env python3
"""Exercise prerequisite consent without installing host packages."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from portable.portable_support import dependencies as deps


class DependenciesTest(unittest.TestCase):
    def setUp(self):
        self.which = patch.object(deps.shutil, "which", side_effect=lambda name: None if name == "cc" else "/usr/bin/" + name)
        self.which.start()
        self.addCleanup(self.which.stop)
        self.tty = patch.object(deps.sys.stdin, "isatty", return_value=True)
        self.tty.start()
        self.addCleanup(self.tty.stop)

    def test_present_never_prompts(self):
        with patch.object(deps.shutil, "which", return_value="/usr/bin/cc"), patch("builtins.input") as prompt, patch.object(deps.subprocess, "run") as run:
            deps.ensure_build_dependencies()
            prompt.assert_not_called()
            run.assert_not_called()

    def test_decline_does_not_install(self):
        with patch("builtins.input", return_value="n"), patch.object(deps.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "not installed"):
                deps.ensure_build_dependencies()
            run.assert_not_called()

    def test_noninteractive_does_not_prompt(self):
        with patch.object(deps.sys.stdin, "isatty", return_value=False), patch("builtins.input") as prompt:
            with self.assertRaisesRegex(RuntimeError, "Noninteractive"):
                deps.ensure_build_dependencies()
            prompt.assert_not_called()

    def test_install_and_recheck(self):
        installed = False

        def which(name):
            return "/usr/bin/" + name if name != "cc" or installed else None

        def install(command, **kwargs):
            nonlocal installed
            self.assertEqual(command, ["sudo", "--", "apt-get", "install", "-y", "build-essential"])
            installed = True

        with patch.object(deps.os, "geteuid", return_value=1000), patch.object(deps.shutil, "which", side_effect=which), patch("builtins.input", return_value="yes"), patch.object(deps.subprocess, "run", side_effect=install):
            deps.ensure_build_dependencies()

    def test_failed_install_propagates(self):
        with patch("builtins.input", return_value="y"), patch.object(deps.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "apt-get")):
            with self.assertRaises(subprocess.CalledProcessError):
                deps.ensure_build_dependencies()

    def test_rechecks_after_successful_package_command(self):
        with patch("builtins.input", return_value="y"), patch.object(deps.subprocess, "run"):
            with self.assertRaisesRegex(RuntimeError, "still missing"):
                deps.ensure_build_dependencies()

    def test_unsupported_package_manager(self):
        with patch.object(deps.shutil, "which", return_value=None), patch("builtins.input") as prompt:
            with self.assertRaisesRegex(RuntimeError, "distribution's package manager"):
                deps.ensure_build_dependencies()
            prompt.assert_not_called()

    def test_remote_consent_and_recheck(self):
        results = [subprocess.CompletedProcess([], 0, json.dumps([False, True, False, True])),
                   subprocess.CompletedProcess([], 0),
                   subprocess.CompletedProcess([], 0, json.dumps([True, True, False, True]))]
        with patch.object(deps.subprocess, "run", side_effect=results) as run, patch("builtins.input", return_value="y"):
            deps.ensure_remote_build_dependencies("example")
            self.assertEqual(run.call_args_list[1].args[0], ["ssh", "-o", "BatchMode=yes", "example", "sudo -n -- apt-get install -y build-essential"])

    def test_remote_noninteractive_never_installs(self):
        result = subprocess.CompletedProcess([], 0, json.dumps([False, True, False, True]))
        with patch.object(deps.subprocess, "run", return_value=result) as run, patch.object(deps.sys.stdin, "isatty", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "noninteractive"):
                deps.ensure_remote_build_dependencies("example")
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
