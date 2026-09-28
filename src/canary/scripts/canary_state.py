"""Validation, state, and filesystem helpers for managed Canary services."""

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
STATE = ROOT / "var/lib/shell-scripts/canary"
CONFIG = ROOT / "etc/fs-tracker"
UNITS = ROOT / "etc/systemd/system"
BIN = ROOT / "usr/local/bin/fs-tracker"


def fail(message):
    raise RuntimeError(message)


def name_path(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        fail("canary name must contain only letters, digits, underscores, and hyphens")
    return STATE / f"{name}.json"


def runtime_path(value, label):
    path = Path(value)
    if not path.is_absolute() or any(char.isspace() or ord(char) < 32 for char in value):
        fail(f"{label} must be an absolute path without whitespace")
    if ".." in path.parts or not path.name:
        fail(f"unsafe {label}: {value}")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            stream.write(content)
        temp.chmod(mode)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def systemctl(*args):
    if ROOT == Path("/"):
        subprocess.run(["systemctl", *args], check=True)


def record_for(name):
    path = name_path(name)
    if path.is_symlink() or not path.is_file():
        fail(f"no managed canary named {name}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("name") != name:
        fail(f"invalid canary state: {path}")
    return record


def owned_files(record):
    name = record["name"]
    return [(CONFIG / f"{name}.conf", record["config_sha256"]),
            (UNITS / f"fs-file-monitor-{name}.service", record["unit_sha256"])]


def verify_owned(record):
    for path, expected in owned_files(record):
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            fail(f"managed file changed or missing: {path}")
