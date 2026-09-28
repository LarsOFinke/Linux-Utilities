"""Template library for canary project profiles."""

from __future__ import annotations

from pathlib import Path


def _read_template_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def get_profile_files(profile: str, project_name: str) -> dict[str, str]:
    template_root = Path(__file__).resolve().parent / profile
    files: dict[str, str] = {}

    for path in sorted(template_root.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(template_root)
        content = _read_template_file(path)
        if path.name == "README.md":
            content = content.replace("{project_name}", project_name)
        files[str(relative)] = content

    return files
