"""Repository locations and safe manifest-relative source paths."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY / "configuration/install.json"


def relative_path(value: str, label: str) -> Path:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[a-zA-Z0-9_./-]+", value)
        or Path(value).is_absolute()
        or ".." in Path(value).parts
        or Path(value) == Path(".")
    ):
        raise SystemExit(f"Invalid {label} in {CATALOG_PATH}: {value!r}")
    return Path(value)


def source_path(manifest: Path, value: str, label: str) -> str:
    return str(manifest.parent / relative_path(value, label))
