"""Validate command ownership and resolve installed components."""

from __future__ import annotations

import re
from pathlib import Path

from catalog.source import source_path

LEGACY_MISSING_COMMANDS = {
    "system": {"h848_wireplumber_05.conf", "h848_wireplumber_04.lua", "h848_audio_guard.service"},
}


def command_definitions(module: str, manifest: Path, source: dict) -> dict:
    commands = source.get("commands")
    if not isinstance(commands, dict) or not commands:
        raise SystemExit(f"Invalid {module}.commands in {manifest}")
    paths = {}
    for name, path in commands.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
            raise SystemExit(f"Invalid command name: {name!r}")
        paths[name] = source_path(manifest, path, f"{module}.commands.{name}")
    helpers = source.get("non_executable_commands", [])
    if not isinstance(helpers, list) or any(name not in commands for name in helpers):
        raise SystemExit(f"Invalid {module}.non_executable_commands in {manifest}")
    components = source.get("components", {})
    if not isinstance(components, dict):
        raise SystemExit(f"Invalid {module}.components in {manifest}")
    claimed: set[str] = set()
    for name, component in components.items():
        if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", name)
                or not isinstance(component, dict)
                or not isinstance(component.get("description"), str)
                or not component["description"].strip()
                or not isinstance(component.get("commands"), list)
                or not component["commands"]
                or any(not isinstance(command, str) or command not in commands
                       for command in component["commands"])
                or len(set(component["commands"])) != len(component["commands"])):
            raise SystemExit(f"Invalid {module}.components.{name} in {manifest}")
        overlap = claimed.intersection(component["commands"])
        if overlap:
            raise SystemExit(f"Commands shared by {module} components: {', '.join(sorted(overlap))}")
        claimed.update(component["commands"])
    if components and (claimed != set(commands) or source.get("pre_remove") or source.get("post_install")
                       or source.get("post_update")
                       or source.get("system_cron")):
        raise SystemExit(f"{module} components must partition commands and have no module lifecycle hooks or cron")
    return {"commands": paths, "non_executable_commands": helpers, "components": components}


def component_commands(module: str, names: set[str], modules: dict) -> set[str]:
    definition = modules[module]
    unknown = names - definition["components"].keys()
    if unknown:
        raise RuntimeError(f"Unknown component for {module}: {', '.join(sorted(unknown))}")
    return {command for name in names for command in definition["components"][name]["commands"]}


def installed_components(module: str, entry: dict, modules: dict) -> set[str]:
    """Infer ownership for registries written before components existed."""
    definitions = modules[module]["components"]
    if not definitions:
        return set()
    recorded = entry.get("components")
    if recorded is not None:
        names = set(recorded)
        component_commands(module, names, modules)
        expected = component_commands(module, names, modules)
        owned = set(entry["commands"])
        if not owned <= expected or not expected - owned <= LEGACY_MISSING_COMMANDS.get(module, set()):
            raise RuntimeError(f"Inconsistent component registry for {module}")
        return names
    owned = set(entry["commands"])
    names = {name for name, item in definitions.items() if owned.intersection(item["commands"])}
    expected = component_commands(module, names, modules)
    if not owned <= expected or not expected - owned <= LEGACY_MISSING_COMMANDS.get(module, set()):
        raise RuntimeError(f"Cannot infer components from legacy registry for {module}")
    return names
