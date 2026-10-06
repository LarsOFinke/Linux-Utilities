"""Files and component ownership chosen for one install transaction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallationPlan:
    desired: dict[str, tuple[set[str], set[str] | None]]
    writing: dict[str, set[str]]
    targets: dict[Path, tuple[str, dict | None]]
    stale: dict[Path, dict]
