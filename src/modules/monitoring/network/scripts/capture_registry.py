#!/usr/bin/env python3
"""Track named capture configurations and check whether recorded processes still run."""

from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def state_path() -> Path:
    return Path(os.environ.get("TCPDUMP_REGISTRY", str(Path.home() / ".local/state/shell-scripts/network-capture.json")))


def read_state(path: Path) -> dict:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symbolic-link registry: {path}")
    if not path.exists():
        return {"schema_version": 1, "profiles": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema_version") != 1 or not isinstance(state.get("profiles"), dict):
        raise RuntimeError(f"Invalid capture registry: {path}")
    return state


def active(entry: dict) -> bool:
    try:
        pid = int(entry["pid"])
        args = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
        capture = os.fsencode(entry["file"])
        return bool(args and Path(os.fsdecode(args[0])).name == "tcpdump" and
                    any(args[index:index + 2] == [b"-w", capture] for index in range(1, len(args) - 1)))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".network-capture-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> None:
    action, *args = sys.argv[1:]
    path = state_path()
    state = read_state(path)
    profiles = state["profiles"]
    if action == "list" and not args:
        for name, entry in sorted(profiles.items()):
            status = "active" if active(entry) else "inactive"
            print(f"{name} [{status}] interface={entry['interface']} file={entry['file']} "
                  f"ports={','.join(entry['ports']) or 'all'} subnets={','.join(entry['subnets']) or 'any'}")
    elif action == "check" and len(args) == 3:
        name, capture_file, pid_file = args
        for other, entry in profiles.items():
            if other != name and entry["file"] == capture_file:
                raise RuntimeError(f"Capture file already belongs to profile {other}: {capture_file}")
            if other != name and entry.get("pid_file") == pid_file:
                raise RuntimeError(f"PID file already belongs to profile {other}: {pid_file}")
    elif action == "stop" and len(args) == 1:
        name = args[0]
        if name not in profiles:
            raise RuntimeError(f"Unknown capture profile: {name}")
        entry = profiles[name]
        if active(entry):
            os.kill(int(entry["pid"]), signal.SIGTERM)
            for _ in range(30):
                if not active(entry):
                    break
                time.sleep(0.1)
            if active(entry):
                raise RuntimeError(f"Capture did not stop: {name}")
        pid_file = Path(entry["pid_file"])
        if not pid_file.is_symlink() and pid_file.is_file() and pid_file.read_text(encoding="utf-8").strip() == str(entry["pid"]):
            pid_file.unlink()
        entry["pid"] = 0
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_state(path, state)
        print(f"Stopped capture profile {name}")
    elif action == "record" and len(args) == 7:
        name, pid, capture_file, pid_file, interface, ports, subnets = args
        for other, entry in profiles.items():
            if other != name and entry["file"] == capture_file:
                raise RuntimeError(f"Capture file already belongs to profile {other}: {capture_file}")
            if other != name and entry.get("pid_file") == pid_file:
                raise RuntimeError(f"PID file already belongs to profile {other}: {pid_file}")
        profiles[name] = {"pid": int(pid), "file": capture_file, "pid_file": pid_file, "interface": interface,
                          "ports": ports.split() if ports else [],
                          "subnets": subnets.split() if subnets else [],
                          "updated_at": datetime.now(timezone.utc).isoformat()}
        write_state(path, state)
    else:
        raise RuntimeError("Usage: capture_registry.py list|check NAME FILE PID_FILE|stop NAME|record NAME PID FILE PID_FILE INTERFACE PORTS SUBNETS")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"Capture registry: {error}", file=sys.stderr)
        sys.exit(1)
