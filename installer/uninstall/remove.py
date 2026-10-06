"""Verify ownership and remove installed modules transactionally."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from catalog import installed_components
from core.files import restore_files, snapshot_files
from core.profile import remove_profile_line
from core.registry import atomic_json, paths, read_registry, registry_lock
from uninstall.hooks import run_pre_remove_hook
from uninstall.plan import managed_paths, selected_commands, verify_files

def uninstall(selected: list[str], registry: dict, registry_path: Path, system: bool,
              base: Path, force: bool, purge_config: bool,
              components: dict[str, set[str] | None] | None = None) -> None:
    with registry_lock(registry_path):
        current = read_registry(registry_path, "system" if system else "user", paths(system)[0])
        missing = set(selected) - current["modules"].keys()
        if missing:
            raise RuntimeError(f"Modules no longer installed: {', '.join(sorted(missing))}")
        if not system and current.get("profile_added") and (base / ".profile").is_symlink():
            raise RuntimeError(f"Refusing symbolic-link profile: {base / '.profile'}")
        _uninstall(selected, current, registry_path, system, base, force, purge_config, components)


def _uninstall(
    selected: list[str],
    registry: dict,
    registry_path: Path,
    system: bool,
    base: Path,
    force: bool,
    purge_config: bool,
    components: dict[str, set[str] | None] | None = None,
) -> None:
    for module in selected:
        entry = registry["modules"][module]
        requested = (components or {}).get(module)
        removing, owned = selected_commands(module, entry, requested)
        verify_files(entry, removing, requested is None, force)
        if requested is None:
            run_pre_remove_hook(module, entry, system, base, purge_config)
        # Hooks can change host services; only managed files and registry are restored.
        files = managed_paths(entry, removing, requested is None) + [registry_path]
        if not system and registry.get("profile_added"):
            files.append(base / ".profile")
        snapshots = snapshot_files(files)
        try:
            remove_managed_files(entry, removing, requested is None)
            publish_removal(module, entry, requested, removing, owned, registry,
                            registry_path, system, base)
        except BaseException as error:
            try:
                restore_files(snapshots)
            except OSError as rollback_error:
                raise RuntimeError(f"Uninstall failed: {error}; rollback failed: {rollback_error}") from error
            raise
        label = module if requested is None else ", ".join(f"{module}:{name}" for name in sorted(requested))
        print(f"Removed {label}")
    print(f"Registry: {registry_path}")


def remove_managed_files(entry: dict, removing: set[str], full_module: bool) -> None:
    for path in managed_paths(entry, removing, full_module):
        if path.is_file() and not path.is_symlink():
            path.unlink()


def publish_removal(module: str, entry: dict, requested: set[str] | None,
                    removing: set[str], owned: set[str], registry: dict,
                    registry_path: Path, system: bool, base: Path) -> None:
    if requested is None or requested == installed_components(module, entry):
        del registry["modules"][module]
    else:
        for name in removing:
            del entry["commands"][name]
        entry["components"] = sorted(owned - requested)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    if not registry["modules"] and not system:
        remove_profile_line(base, registry)
    atomic_json(registry_path, registry)
