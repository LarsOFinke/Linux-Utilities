"""Manage only the PATH line added by user installation."""

from __future__ import annotations

import os
from pathlib import Path

from core.files import restore_files

DEFAULT_PROFILE_LINE = 'export PATH="$HOME/.local/bin:$PATH" # shell-scripts setup'

def ensure_user_path(home: Path, registry: dict, bin_dir: Path) -> Path | None:
    if str(bin_dir) in os.environ.get("PATH", "").split(os.pathsep):
        return None
    relative_bin = bin_dir.relative_to(home)
    profile_line = f'export PATH="$HOME/{relative_bin}:$PATH" # shell-scripts setup'
    profile = home / ".profile"
    content = profile.read_text(encoding="utf-8") if profile.exists() else ""
    if profile_line not in content:
        with profile.open("a", encoding="utf-8") as stream:
            stream.write(("" if not content or content.endswith("\n") else "\n") + profile_line + "\n")
        registry["profile_added"] = True
        registry["profile_line"] = profile_line
    return profile


def remove_profile_line(home: Path, registry: dict) -> None:
    if not registry.get("profile_added"):
        return
    profile = home / ".profile"
    if profile.is_symlink():
        raise RuntimeError(f"Refusing symbolic-link profile: {profile}")
    if not profile.exists():
        return
    lines = profile.read_text(encoding="utf-8").splitlines()
    profile_line = registry.get("profile_line", DEFAULT_PROFILE_LINE)
    content = ("\n".join(line for line in lines if line != profile_line) + "\n").encode("utf-8")
    restore_files({profile: (content, profile.stat().st_mode & 0o777)})
    registry["profile_added"] = False
