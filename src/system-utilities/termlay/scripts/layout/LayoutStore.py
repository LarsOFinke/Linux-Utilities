"""Private JSON storage for named layouts."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from Layout import Layout
from TermlayError import TermlayError
from layout_paths import NAME_PATTERN, config_directory, validate_name


class LayoutStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else config_directory()

    def path(self, name: str) -> Path:
        validate_name(name)
        return self.directory / f"{name}.json"

    def check_directory(self) -> None:
        if self.directory.is_symlink():
            raise TermlayError(f"refusing symbolic-link layout directory: {self.directory}")

    def save(self, layout: Layout) -> None:
        self._write(layout, replace_existing=False)

    def replace(self, layout: Layout) -> None:
        self._write(layout, replace_existing=True)

    def _write(self, layout: Layout, replace_existing: bool) -> None:
        path = self.path(layout.name)
        self.check_directory()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.check_directory()
        descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fchmod(descriptor, 0o700)
        finally:
            os.close(descriptor)
        if path.is_symlink():
            raise TermlayError(f"refusing symbolic-link layout: {path}")
        if replace_existing and not path.is_file():
            raise TermlayError(f"layout '{layout.name}' not found")
        if path.exists() and not replace_existing:
            raise TermlayError(f"layout '{layout.name}' already exists; use 'termlay update' to replace it")
        descriptor, temporary = tempfile.mkstemp(prefix=".termlay-", suffix=".json", dir=self.directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(layout.to_json(), stream, indent=2)
                stream.write("\n")
            os.chmod(temporary, 0o600)
            if replace_existing:
                if path.is_symlink():
                    raise TermlayError(f"refusing symbolic-link layout: {path}")
                if not path.is_file():
                    raise TermlayError(f"layout '{layout.name}' no longer exists")
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
        except FileExistsError as error:
            raise TermlayError(f"layout '{layout.name}' already exists; use 'termlay update' to replace it") from error
        finally:
            Path(temporary).unlink(missing_ok=True)

    def load(self, name: str) -> Layout:
        path = self.path(name)
        self.check_directory()
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
        self.check_directory()
        if not self.directory.exists():
            return []
        return sorted(path.stem for path in self.directory.glob("*.json")
                      if NAME_PATTERN.fullmatch(path.stem) and path.is_file() and not path.is_symlink())

    def delete(self, name: str) -> None:
        path = self.path(name)
        self.check_directory()
        if path.is_symlink():
            raise TermlayError(f"refusing symbolic-link layout: {path}")
        try:
            path.unlink()
        except FileNotFoundError as error:
            raise TermlayError(f"layout '{name}' not found") from error
