"""Atomic file publication and rollback helpers."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_command(source: Path, target: Path, executable: bool) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".shell-scripts.", dir=target.parent)
    os.close(descriptor)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o755 if executable else 0o644)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def snapshot_files(paths: list[Path]) -> dict[Path, tuple[bytes, int] | None]:
    """Capture managed file bytes and modes before a transaction changes them."""
    return {
        path: (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
        for path in paths
    }


def restore_files(snapshots: dict[Path, tuple[bytes, int] | None]) -> None:
    for path, original in reversed(list(snapshots.items())):
        if original is None:
            path.unlink(missing_ok=True)
            continue
        contents, mode = original
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".shell-scripts-restore.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(contents)
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
