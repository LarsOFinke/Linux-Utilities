"""Plan an install and reject unsafe ownership before changing files."""

from __future__ import annotations

from pathlib import Path

from catalog import REPOSITORY, component_commands, installed_components
from core.files import sha256
from core.registry import paths
from setup.InstallationPlan import InstallationPlan


def plan_installation(selected: list[str], registry: dict, bin_dir: Path, system: bool,
                      components: dict[str, set[str] | None] | None, definitions: dict) -> InstallationPlan:
    desired = {}
    writing = {}
    for module in selected:
        definition = definitions[module]
        requested = (components or {}).get(module)
        if requested is None or not definition["components"]:
            desired[module] = (set(definition["commands"]),
                               set(definition["components"]) if definition["components"] else None)
            writing[module] = set(definition["commands"])
        else:
            previous = registry["modules"].get(module)
            names = set(requested) | (installed_components(module, previous) if previous else set())
            desired[module] = (component_commands(module, names), names)
            writing[module] = component_commands(module, requested)
    verify_sources(selected, writing, system, definitions)
    targets, stale = owned_paths(selected, writing, desired, registry, bin_dir, system,
                                 components, definitions)
    verify_ownership(selected, registry, targets, stale)
    return InstallationPlan(desired, writing, targets, stale)


def verify_sources(selected: list[str], writing: dict[str, set[str]], system: bool,
                   definitions: dict) -> None:
    scope = "system" if system else "user"
    for module in selected:
        definition = definitions[module]
        if scope not in definition["scopes"]:
            raise RuntimeError(f"{module} does not support {scope} installation; choose a supported scope.")
        sources = [definition["manifest"], definition["setup"], definition["documentation"]]
        sources.extend(definition["commands"][name] for name in writing[module])
        sources.extend(script for name, script in definition.get("build_commands", {}).items()
                       if name in writing[module])
        sources.extend(definition["examples"])
        sources.extend(definition["cron_templates"])
        if system and "system_cron" in definition:
            sources.append(definition["system_cron"]["source"])
        for source in sources:
            if not (REPOSITORY / source).is_file():
                raise RuntimeError(f"Missing source file for {module}: {source}")


def owned_paths(selected: list[str], writing: dict[str, set[str]],
                desired: dict[str, tuple[set[str], set[str] | None]], registry: dict,
                bin_dir: Path, system: bool, components: dict[str, set[str] | None] | None,
                definitions: dict) -> tuple[dict[Path, tuple[str, dict | None]], dict[Path, dict]]:
    targets: dict[Path, tuple[str, dict | None]] = {}
    stale: dict[Path, dict] = {}
    for module in selected:
        definition = definitions[module]
        previous = registry["modules"].get(module, {}).get("commands", {})
        for name in writing[module]:
            target = bin_dir / name
            if target in targets:
                raise RuntimeError(f"Selected modules share a command path: {target}")
            targets[target] = (module, previous.get(name))
        for name, recorded in previous.items():
            obsolete = ((components is None or components.get(module) is None)
                        and name not in desired[module][0])
            if obsolete:
                target = Path(recorded["path"])
                if target != bin_dir / name:
                    raise RuntimeError(f"Unexpected recorded command path: {target}")
                stale[target] = recorded
        previous_cron = registry["modules"].get(module, {}).get("managed_cron_files", {})
        if system and "system_cron" in definition:
            cron_name = definition["system_cron"]["name"]
            cron_target = paths(True)[2] / "etc/cron.d" / cron_name
            if cron_target in targets:
                raise RuntimeError(f"Selected modules share a cron path: {cron_target}")
            targets[cron_target] = (module, previous_cron.get(str(cron_target)))
        for path, recorded in previous_cron.items():
            if not system or "system_cron" not in definition or path != str(cron_target):
                stale[Path(path)] = recorded
    return targets, stale


def verify_ownership(selected: list[str], registry: dict,
                     targets: dict[Path, tuple[str, dict | None]], stale: dict[Path, dict]) -> None:
    for other, entry in registry["modules"].items():
        if other in selected:
            continue
        for record in entry["commands"].values():
            if Path(record["path"]) in targets or Path(record["path"]) in stale:
                raise RuntimeError(f"Installed modules share an owned path: {record['path']}")
        for path in entry.get("managed_cron_files", {}):
            if Path(path) in targets or Path(path) in stale:
                raise RuntimeError(f"Installed modules share an owned path: {path}")
    if stale.keys() & targets.keys():
        raise RuntimeError("An obsolete file is also used by a selected module; uninstall first.")
    for target, (_, recorded) in targets.items():
        if target.is_symlink() or (target.exists() and not recorded):
            raise RuntimeError(f"Refusing to replace an unmanaged file: {target}")
        if target.exists() and recorded and sha256(target) != recorded["sha256"]:
            raise RuntimeError(f"Installed file changed locally: {target}")
    for target, record in stale.items():
        if target.is_symlink():
            raise RuntimeError(f"Refusing symbolic-link obsolete file: {target}")
        if target.exists() and sha256(target) != record["sha256"]:
            raise RuntimeError(f"Obsolete installed file changed locally: {target}")
