"""Own the SSH watcher configuration and systemd service."""

import json
import os
import re
import subprocess
from pathlib import Path

from canary_ssh_events import EVENTS
from canary_state import ROOT, UNITS, atomic_write, digest, fail, runtime_path, systemctl

STATE = ROOT / "var/lib/shell-scripts/canary/ssh/record.json"
CONFIG = ROOT / "etc/fs-tracker/ssh-watch.json"
UNIT = UNITS / "fs-ssh-watch.service"
BIN = ROOT / "usr/local/bin/canary-ssh-watcher"


def record():
    if STATE.is_symlink() or not STATE.is_file():
        fail("SSH watcher is not configured")
    data = json.loads(STATE.read_text(encoding="utf-8"))
    if data.get("kind") != "ssh":
        fail(f"invalid SSH watcher state: {STATE}")
    return data


def verify(data):
    for path, key in ((CONFIG, "config_sha256"), (UNIT, "unit_sha256")):
        if path.is_symlink() or not path.is_file() or digest(path) != data.get(key):
            fail(f"managed file changed or missing: {path}")


def validate(events, scope, user, log, action):
    chosen = list(dict.fromkeys(events))
    if not chosen or any(event not in EVENTS for event in chosen):
        fail(f"choose at least one event from: {', '.join(EVENTS)}")
    if scope not in ("user", "system") or (scope == "user" and not user) or (scope == "system" and user):
        fail("choose --system or --user LOGIN")
    if user and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", user):
        fail("invalid login account name")
    log_path = runtime_path(log, "log")
    action_path = runtime_path(action, "action") if action else None
    if action_path and (not action_path.is_file() or not os.access(action_path, os.X_OK)):
        fail(f"action must be executable: {action_path}")
    if log_path.exists() and (log_path.is_symlink() or not log_path.is_file()):
        fail(f"log must be a regular file: {log_path}")
    return {"events": chosen, "scope": scope, "user": user if scope == "user" else None,
            "log": str(log_path), "action": str(action_path) if action_path else None}


def _unit_text():
    return ("[Unit]\nDescription=Canary SSH journal watcher\nAfter=systemd-journald.service\n\n"
            "[Service]\nType=simple\nUMask=0077\n"
            f"ExecStart={BIN} --config {CONFIG}\nRestart=on-failure\n"
            "NoNewPrivileges=yes\nProtectHome=yes\n\n"
            "[Install]\nWantedBy=multi-user.target\n")


def _write_state():
    atomic_write(STATE, json.dumps({"kind": "ssh", "config_sha256": digest(CONFIG),
                                    "unit_sha256": digest(UNIT)}, indent=2) + "\n", 0o600)


def configure(settings):
    if not BIN.is_file() or BIN.is_symlink():
        fail(f"install the canary module first: {BIN}")
    for path in (STATE, CONFIG, UNIT):
        if path.exists() or path.is_symlink():
            fail(f"refusing to replace existing file: {path}")
    Path(settings["log"]).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        atomic_write(CONFIG, json.dumps(settings, indent=2) + "\n", 0o600)
        atomic_write(UNIT, _unit_text(), 0o644)
        _write_state()
        systemctl("daemon-reload")
        systemctl("enable", "--now", UNIT.name)
    except BaseException:
        if ROOT == Path("/"):
            subprocess.run(["systemctl", "disable", "--now", UNIT.name], check=False)
        for path in (STATE, CONFIG, UNIT):
            path.unlink(missing_ok=True)
        raise
    print(f"Configured SSH watcher: {UNIT.name}")


def update(settings):
    data = record()
    verify(data)
    previous_config = CONFIG.read_text(encoding="utf-8")
    previous_state = STATE.read_text(encoding="utf-8")
    Path(settings["log"]).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        atomic_write(CONFIG, json.dumps(settings, indent=2) + "\n", 0o600)
        _write_state()
        systemctl("restart", UNIT.name)
    except BaseException:
        atomic_write(CONFIG, previous_config, 0o600)
        atomic_write(STATE, previous_state, 0o600)
        if ROOT == Path("/"):
            subprocess.run(["systemctl", "restart", UNIT.name], check=False)
        raise
    print(f"Updated SSH watcher: {UNIT.name}")


def remove():
    data = record()
    verify(data)
    systemctl("disable", "--now", UNIT.name)
    CONFIG.unlink()
    UNIT.unlink()
    STATE.unlink()
    systemctl("daemon-reload")
    print("Removed SSH watcher; log retained")
