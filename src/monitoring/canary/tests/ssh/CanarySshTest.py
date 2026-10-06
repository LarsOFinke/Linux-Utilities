"""Check SSH event selection and isolated service ownership."""

import json
import os
import pty
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MODULE / "scripts/ssh"))
sys.path.insert(0, str(MODULE / "scripts"))
from canary_ssh_events import classify, selected
import canary_ssh_lifecycle
import canary_ssh_watcher


class CanarySshTest(unittest.TestCase):
    def test_main_setup_and_update_offer_ssh_choices(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            log = Path(temporary) / "ssh.jsonl"
            env = dict(os.environ, SHELL_SCRIPTS_INSTALL_ROOT=str(root), PYTHONDONTWRITEBYTECODE="1")

            def interactive(*arguments, replies):
                master, slave = pty.openpty()
                try:
                    process = subprocess.Popen([str(MODULE.parents[2] / "main.sh"), *arguments],
                                               env=env, stdin=slave, stdout=subprocess.DEVNULL,
                                               stderr=subprocess.PIPE, text=True)
                    os.close(slave)
                    slave = -1
                    os.write(master, replies.encode("utf-8"))
                    _, errors = process.communicate(timeout=30)
                    self.assertEqual(process.returncode, 0, errors)
                finally:
                    if slave != -1:
                        os.close(slave)
                    os.close(master)

            interactive("setup", "--system", "--module", "canary",
                        replies=f"y\nsuccess\nuser\nalice\n{log}\n")
            config = root / "etc/fs-tracker/ssh-watch.json"
            self.assertEqual(json.loads(config.read_text())["user"], "alice")
            interactive("update", "--system", "--module", "canary",
                        replies=f"y\nfailure\nsystem\n{log}\n")
            settings = json.loads(config.read_text())
            self.assertEqual(settings["events"], ["failure"])
            self.assertEqual(settings["scope"], "system")

    def test_journal_event_types_and_account_filter(self):
        cases = {
            "Connection from 192.0.2.1 port 22 on 192.0.2.2 port 22": ("attempt", None),
            "Accepted publickey for alice from 192.0.2.1 port 22 ssh2": ("success", "alice"),
            "Failed password for alice from 192.0.2.1 port 22 ssh2": ("failure", "alice"),
            "Invalid user stranger from 192.0.2.1 port 22": ("invalid-user", "stranger"),
            "Disconnected from user alice 192.0.2.1 port 22": ("disconnect", "alice"),
            "pam_unix(sshd:session): session opened for user alice(uid=1000) by (uid=0)":
                ("session-open", "alice"),
            "pam_unix(sshd:session): session closed for user alice": ("session-close", "alice"),
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                event = classify({"SYSLOG_IDENTIFIER": "sshd", "MESSAGE": message})
                self.assertEqual((event["event"], event["user"]), expected)
                self.assertTrue(selected(event, {"events": [expected[0]], "scope": "system", "user": None}))
                self.assertEqual(selected(event, {"events": [expected[0]], "scope": "user", "user": "alice"}),
                                 expected[1] == "alice")
        self.assertIsNone(classify({"SYSLOG_IDENTIFIER": "other", "MESSAGE": "Accepted password for alice from x"}))

    def test_setup_update_and_module_removal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            env = dict(os.environ, SHELL_SCRIPTS_INSTALL_ROOT=str(root), PYTHONDONTWRITEBYTECODE="1")
            def run(*args, success=True):
                result = subprocess.run(args, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                return result

            run(str(MODULE.parents[2] / "main.sh"), "setup", "--system", "--module", "canary", "--no-configure")
            command = root / "usr/local/bin/canary-ssh"
            log = root / "var/log/fs-tracker/ssh.jsonl"
            run(str(command), "setup", "--events", "attempt,success", "--user", "alice", "--log", str(log))
            config = root / "etc/fs-tracker/ssh-watch.json"
            unit = root / "etc/systemd/system/fs-ssh-watch.service"
            self.assertEqual(json.loads(config.read_text())["user"], "alice")
            run(str(command), "update", "--events", "failure,disconnect", "--system")
            self.assertEqual(json.loads(config.read_text())["events"], ["failure", "disconnect"])
            self.assertIsNone(json.loads(config.read_text())["user"])
            run(str(MODULE.parents[2] / "main.sh"), "update", "--system", "--module", "canary", "--no-configure")
            self.assertTrue(unit.is_file())
            run(str(MODULE.parents[2] / "main.sh"), "uninstall", "--system", "--module", "canary")
            self.assertFalse(unit.exists())
            self.assertFalse(config.exists())

    def test_watcher_writes_only_selected_events_and_passes_action_json(self):
        class FakeJournal:
            def __enter__(self):
                self.stdout = iter((
                    json.dumps({"SYSLOG_IDENTIFIER": "sshd", "MESSAGE":
                                "Accepted publickey for alice from 192.0.2.1 port 22 ssh2"}) + "\n",
                    json.dumps({"SYSLOG_IDENTIFIER": "sshd", "MESSAGE":
                                "Failed password for bob from 192.0.2.2 port 22 ssh2"}) + "\n",
                ))
                return self

            def __exit__(self, *_):
                return False

            def wait(self):
                return 0

        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "events.jsonl"
            config = {"events": ["success", "failure"], "scope": "user", "user": "alice",
                      "log": str(log), "action": "/test-action"}
            with patch.object(canary_ssh_watcher.subprocess, "Popen", return_value=FakeJournal()) as journal, \
                    patch.object(canary_ssh_watcher.subprocess, "run") as action:
                action.return_value.returncode = 0
                canary_ssh_watcher.watch(config)
            self.assertEqual(journal.call_args.args[0][:3], ["journalctl", "--follow", "--lines=0"])
            events = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["user"], "alice")
            self.assertEqual(json.loads(action.call_args.kwargs["input"]), events[0])

    def test_service_failure_rolls_back_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "canary-ssh-watcher"
            binary.write_text("stub")
            config = root / "config/ssh-watch.json"
            unit = root / "units/fs-ssh-watch.service"
            state = root / "state/record.json"
            settings = {"events": ["success"], "scope": "user", "user": "alice",
                        "log": str(root / "logs/events.jsonl"), "action": None}
            with patch.multiple(canary_ssh_lifecycle, ROOT=Path("/"), BIN=binary,
                                CONFIG=config, UNIT=unit, STATE=state), \
                    patch.object(canary_ssh_lifecycle.subprocess, "run") as cleanup:
                with patch.object(canary_ssh_lifecycle, "systemctl",
                                  side_effect=[None, RuntimeError("cannot start")]):
                    with self.assertRaisesRegex(RuntimeError, "cannot start"):
                        canary_ssh_lifecycle.configure(settings)
                self.assertFalse(any(path.exists() for path in (config, unit, state)))
                cleanup.assert_called_once()
                with patch.object(canary_ssh_lifecycle, "systemctl"):
                    canary_ssh_lifecycle.configure(settings)
                old_config = config.read_bytes()
                old_state = state.read_bytes()
                revised = dict(settings, events=["failure"])
                with patch.object(canary_ssh_lifecycle, "systemctl", side_effect=RuntimeError("cannot restart")):
                    with self.assertRaisesRegex(RuntimeError, "cannot restart"):
                        canary_ssh_lifecycle.update(revised)
                self.assertEqual(config.read_bytes(), old_config)
                self.assertEqual(state.read_bytes(), old_state)


if __name__ == "__main__":
    unittest.main()
