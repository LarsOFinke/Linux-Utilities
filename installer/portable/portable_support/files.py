"""Safe local paths, atomic writes, and file ownership checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from .state import fail


def local_path(value: str, module: Path) -> Path:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", value):
        fail(f"Invalid module path: {value!r}")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        fail(f"Unsafe module path: {value!r}")
    return module / path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_copy(source: Path, target: Path, executable: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".module-install-", dir=target.parent)
    os.close(descriptor)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o755 if executable else 0o644)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".module-state-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def restore_snapshot(path: Path, original: tuple[bytes, int] | None) -> None:
    if original is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".module-restore-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(original[0])
        os.chmod(temporary, original[1])
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def check_target(path: Path, record: dict | None, force: bool = False) -> None:
    if path.is_symlink():
        fail(f"Refusing symbolic-link file: {path}")
    if path.exists() and record is None:
        fail(f"Refusing unmanaged file: {path}")
    if path.exists() and record and not force and digest(path) != record["sha256"]:
        fail(f"Installed file changed locally: {path}")
