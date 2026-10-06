"""Resolve and verify the files a removal is allowed to touch."""

from __future__ import annotations

from pathlib import Path

from catalog import component_commands, installed_components
from core.files import sha256


def selected_commands(module: str, entry: dict, requested: set[str] | None) -> tuple[set[str], set[str]]:
    if requested is None:
        return set(entry["commands"]), set()
    owned = installed_components(module, entry)
    if not requested <= owned:
        raise RuntimeError(f"Component is not installed for {module}: {', '.join(sorted(requested - owned))}")
    return component_commands(module, requested), owned


def verify_files(entry: dict, removing: set[str], full_module: bool, force: bool) -> None:
    for name in removing:
        record = entry["commands"][name]
        target = Path(record["path"])
        if target.is_symlink():
            raise RuntimeError(f"Refusing symbolic-link command: {target}")
        if target.exists() and not force and sha256(target) != record["sha256"]:
            raise RuntimeError(f"Installed command changed locally: {target}; use --force to remove it.")
    for path, record in (entry.get("managed_cron_files", {}) if full_module else {}).items():
        target = Path(path)
        if target.is_symlink():
            raise RuntimeError(f"Refusing symbolic-link cron file: {target}")
        if target.exists() and not force and sha256(target) != record["sha256"]:
            raise RuntimeError(f"Installed cron file changed locally: {target}; use --force to remove it.")


def managed_paths(entry: dict, removing: set[str], full_module: bool) -> list[Path]:
    paths = [Path(entry["commands"][name]["path"]) for name in removing]
    if full_module:
        paths.extend(Path(path) for path in entry.get("managed_cron_files", {}))
    return paths
