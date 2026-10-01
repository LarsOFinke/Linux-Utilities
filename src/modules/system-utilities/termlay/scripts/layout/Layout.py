"""A named, ordered collection of terminal working directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from TermlayError import TermlayError

VERSION = 1


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
