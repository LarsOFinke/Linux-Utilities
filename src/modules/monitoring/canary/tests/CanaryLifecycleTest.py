"""Check service-configuration rollback with isolated files and mocked systemd."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import canary_lifecycle
import canary_state


class CanaryLifecycleTest(unittest.TestCase):
    def test_failed_or_interrupted_configuration_can_be_retried(self):
        for error_type in (RuntimeError, KeyboardInterrupt):
            for failed_call in (1, 2):
                with self.subTest(error=error_type, call=failed_call), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    binary = root / "fs-tracker"
                    binary.write_text("stub")
                    target = root / "decoy"
                    target.write_text("keep target")
                    log = root / "events.jsonl"
                    log.write_text("keep log")
                    args = SimpleNamespace(name="demo", path=str(target), log=str(log), action=None)
                    error = error_type("injected systemd failure")
                    effects = [None] * (failed_call - 1) + [error]
                    with patch.multiple(canary_lifecycle, ROOT=Path("/"), BIN=binary,
                                        CONFIG=root / "config", UNITS=root / "units"), \
                            patch.object(canary_state, "STATE", root / "state"), \
                            patch.object(canary_lifecycle.subprocess, "run") as cleanup:
                        with patch.object(canary_lifecycle, "systemctl", side_effect=effects):
                            with self.assertRaises(error_type) as raised:
                                canary_lifecycle.configure(args)
                            self.assertIs(raised.exception, error)
                        cleanup.assert_called_once_with(
                            ["systemctl", "disable", "--now", "fs-file-monitor-demo.service"], check=False)
                        for path in (root / "config/demo.conf", root / "units/fs-file-monitor-demo.service",
                                     root / "state/demo.json"):
                            self.assertFalse(path.exists())
                        self.assertEqual(target.read_text(), "keep target")
                        self.assertEqual(log.read_text(), "keep log")
                        with patch.object(canary_lifecycle, "systemctl"):
                            canary_lifecycle.configure(args)
                        self.assertTrue((root / "state/demo.json").is_file())


if __name__ == "__main__":
    unittest.main()
