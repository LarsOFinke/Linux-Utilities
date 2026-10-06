"""Validate and apply a module installation transaction."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

from catalog import MODULES, REPOSITORY
from core.files import copy_command, restore_files, sha256, snapshot_files
from core.profile import ensure_user_path
from core.registry import atomic_json, paths, read_registry, registry_lock
from setup.plan import plan_installation

def install(selected: list[str], registry: dict, bin_dir: Path, registry_path: Path, system: bool,
            built: dict[tuple[str, str], Path] | None = None,
            components: dict[str, set[str] | None] | None = None) -> None:
    with registry_lock(registry_path):
        current = read_registry(registry_path, "system" if system else "user", bin_dir)
        apply_installation(selected, current, bin_dir, registry_path, system, built, components)


def apply_installation(selected: list[str], registry: dict, bin_dir: Path, registry_path: Path, system: bool,
            built: dict[tuple[str, str], Path] | None = None,
            components: dict[str, set[str] | None] | None = None,
            updating: bool = False) -> None:
    plan = plan_installation(selected, registry, bin_dir, system, components, MODULES)
    changes = copy.deepcopy(registry)
    profile = Path.home() / ".profile"
    if not system and profile.is_symlink():
        raise RuntimeError(f"Refusing symbolic-link profile: {profile}")
    files = list(plan.targets) + list(plan.stale) + [registry_path]
    if not system:
        files.append(profile)
    snapshots = snapshot_files(files)
    profile_notice = None
    try:
        bin_dir.mkdir(parents=True, exist_ok=True)
        for module in selected:
            previous = changes["modules"].get(module, {}).get("commands", {})
            changes["modules"][module] = write_module(
                module, previous, plan.writing[module], plan.desired[module],
                built, bin_dir, system, components
            )
        for target in plan.stale:
            target.unlink(missing_ok=True)
        changes["repository"] = str(REPOSITORY)
        changes["updated_at"] = datetime.now(timezone.utc).isoformat()
        if not system and not updating:
            profile_notice = ensure_user_path(Path.home(), changes, bin_dir)
        atomic_json(registry_path, changes)
    except BaseException as error:
        try:
            restore_files(snapshots)
        except OSError as rollback_error:
            raise RuntimeError(f"Install failed: {error}; rollback failed: {rollback_error}") from error
        raise
    if profile_notice is not None:
        print(f"Open a new shell or run: source {profile_notice}")
    verb = "Updated" if updating else "Installed"
    for module in selected:
        definition = MODULES[module]
        print(f"{verb} {module}: {', '.join(name for name in definition['commands'] if name in plan.writing[module] and name not in definition.get('non_executable_commands', []))}")
    print(f"Registry: {registry_path}")


def write_module(module: str, previous_commands: dict, writing: set[str],
                 desired: tuple[set[str], set[str] | None],
                 built: dict[tuple[str, str], Path] | None, bin_dir: Path, system: bool,
                 components: dict[str, set[str] | None] | None) -> dict:
    definition = MODULES[module]
    commands = ({} if components is None or components.get(module) is None
                else copy.deepcopy(previous_commands))
    for name, source_relative in definition["commands"].items():
        if name not in writing:
            continue
        source = (built or {}).get((module, name), REPOSITORY / source_relative)
        target = bin_dir / name
        copy_command(source, target, name not in definition.get("non_executable_commands", []))
        source = REPOSITORY / source_relative
        commands[name] = {"path": str(target), "source": str(source),
                          "sha256": sha256(target), "source_sha256": sha256(source)}
    managed_cron_files = {}
    if system and "system_cron" in definition:
        cron = definition["system_cron"]
        cron_target = paths(True)[2] / "etc/cron.d" / cron["name"]
        cron_target.parent.mkdir(parents=True, exist_ok=True)
        source = REPOSITORY / cron["source"]
        copy_command(source, cron_target, False)
        managed_cron_files[str(cron_target)] = {"source": str(source), "sha256": sha256(cron_target)}
    scope = "system" if system else "user"
    base = paths(system)[2]
    entry = {
        "commands": commands,
        "setup_script": str(REPOSITORY / definition["setup"]),
        "documentation": str(REPOSITORY / definition["documentation"]),
        "config_examples": [str(REPOSITORY / item) for item in definition["examples"]],
        "cron_templates": [str(REPOSITORY / item) for item in definition["cron_templates"]],
        "managed_cron_files": managed_cron_files,
        "runtime_configs": [str(base / item) for item in definition.get("runtime_configs", {}).get(scope, [])],
        "schedules": [item if item.startswith("user crontab:") else str(base / item)
                      for item in definition.get("schedules", {}).get(scope, [])],
        "pre_remove": definition.get("pre_remove"),
    }
    if desired[1] is not None:
        entry["components"] = sorted(desired[1])
    return entry
