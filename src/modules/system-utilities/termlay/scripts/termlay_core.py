"""Validated layouts and private JSON storage for termlay."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

VERSION = 1
NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


class TermlayError(Exception):
    """An expected error suitable for display by the CLI."""


@dataclass(frozen=True)
class Layout:
    name: str
    directories: tuple[Path, ...]

    def to_json(self) -> dict:
        return {"version": VERSION, "name": self.name,
                "tabs": [{"cwd": str(directory)} for directory in self.directories]}

    @classmethod
    def from_json(cls, data: object, expected_name: str) -> "Layout":
        if (not isinstance(data, dict) or type(data.get("version")) is not int
                or data["version"] != VERSION or data.get("name") != expected_name):
            raise TermlayError(f"invalid layout '{expected_name}': unsupported version or name")
        tabs = data.get("tabs")
        if not isinstance(tabs, list) or not tabs:
            raise TermlayError(f"invalid layout '{expected_name}': expected a nonempty tabs list")
        directories = []
        for index, tab in enumerate(tabs, 1):
            if (not isinstance(tab, dict) or not isinstance(tab.get("cwd"), str)
                    or not tab["cwd"] or "\0" in tab["cwd"]):
                raise TermlayError(f"invalid layout '{expected_name}': tab {index} has no directory")
            directory = Path(tab["cwd"])
            if not directory.is_absolute():
                raise TermlayError(f"invalid layout '{expected_name}': tab {index} has a relative directory")
            directories.append(directory)
        return cls(expected_name, tuple(directories))


class TerminalBackend(Protocol):
    def open_layout(self, layout: Layout) -> None:
        """Open tabs in layout order."""


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
    directories = []
    for raw in paths:
        try:
            directory = Path(raw).expanduser().resolve()
        except (OSError, RuntimeError) as error:
            raise TermlayError(f"cannot resolve directory {raw}: {error}") from error
        if not directory.is_dir():
            raise TermlayError(f"not an existing directory: {raw}")
        directories.append(directory)
    return Layout(name, tuple(directories))


def missing_directories(layout: Layout) -> list[Path]:
    return [directory for directory in layout.directories if not directory.is_dir()]


class LayoutStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else config_directory()

    def path(self, name: str) -> Path:
        validate_name(name)
        return self.directory / f"{name}.json"

    def save(self, layout: Layout, force: bool = False) -> None:
        path = self.path(layout.name)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        if path.is_symlink():
            raise TermlayError(f"refusing symbolic-link layout: {path}")
        if path.exists() and not force:
            raise TermlayError(f"layout '{layout.name}' already exists; use --force to overwrite")
        descriptor, temporary = tempfile.mkstemp(prefix=".termlay-", suffix=".json", dir=self.directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(layout.to_json(), stream, indent=2)
                stream.write("\n")
            os.chmod(temporary, 0o600)
            if force:
                if path.is_symlink():
                    raise TermlayError(f"refusing symbolic-link layout: {path}")
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
        except FileExistsError as error:
            raise TermlayError(f"layout '{layout.name}' already exists; use --force to overwrite") from error
        finally:
            Path(temporary).unlink(missing_ok=True)

    def load(self, name: str) -> Layout:
        path = self.path(name)
        if path.is_symlink():
            raise TermlayError(f"refusing symbolic-link layout: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise TermlayError(f"layout '{name}' not found") from error
        except (UnicodeError, json.JSONDecodeError) as error:
            raise TermlayError(f"invalid layout '{name}': {error}") from error
        return Layout.from_json(data, name)

    def list_names(self) -> list[str]:
        if not self.directory.exists():
            return []
        return sorted(path.stem for path in self.directory.glob("*.json")
                      if NAME_PATTERN.fullmatch(path.stem) and path.is_file() and not path.is_symlink())

    def delete(self, name: str) -> None:
        path = self.path(name)
        if path.is_symlink():
            raise TermlayError(f"refusing symbolic-link layout: {path}")
        try:
            path.unlink()
        except FileNotFoundError as error:
            raise TermlayError(f"layout '{name}' not found") from error
