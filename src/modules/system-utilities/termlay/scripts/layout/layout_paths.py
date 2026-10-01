"""Validate layout names and working directory paths."""

from __future__ import annotations

import os
import re
from pathlib import Path

from Layout import Layout
from TermlayError import TermlayError

NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


def validate_name(name: str) -> None:
    if not NAME_PATTERN.fullmatch(name):
        raise TermlayError("layout name must start with a letter or digit and contain only letters, digits, _ or -")


def config_directory() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    if configured:
        base = Path(configured).expanduser()
        if not base.is_absolute():
            raise TermlayError("XDG_CONFIG_HOME must be an absolute path")
    else:
        base = Path.home() / ".config"
    return base / "termlay" / "layouts"


def layout_from_paths(name: str, paths: list[str]) -> Layout:
    validate_name(name)
    if not paths:
        raise TermlayError("save requires at least one directory")
    return Layout(name, tuple(resolve_directory(raw) for raw in paths))


def resolve_directory(raw: str) -> Path:
    try:
        directory = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError) as error:
        raise TermlayError(f"cannot resolve directory {raw}: {error}") from error
    if not directory.is_dir():
        raise TermlayError(f"not an existing directory: {raw}")
    return directory


def missing_directories(layout: Layout) -> list[Path]:
    return [directory for directory in layout.directories if not directory.is_dir()]
