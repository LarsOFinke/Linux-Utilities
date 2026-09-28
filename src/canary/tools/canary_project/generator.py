#!/usr/bin/env python3
"""Generate a realistic, passive canary project for defensive reconnaissance testing."""

from __future__ import annotations

from pathlib import Path

from .templates import get_profile_files


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_project(project_name: str, output_dir: str | Path, mode: str) -> Path:
    root = Path(output_dir).resolve() / project_name
    root.mkdir(parents=True, exist_ok=True)

    for rel_path, content in get_profile_files(mode, project_name).items():
        write_file(root / rel_path, content)

    return root
