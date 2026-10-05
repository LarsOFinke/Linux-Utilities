"""Shared inventory, scope routing, and selection for installed modules."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from catalog import MODULES, choose_categorized_modules, choose_modules
from manage import paths, read_registry, registry_inventory
from remote_deploy import cached, scan_remote, valid_target

MANAGER = Path(__file__).with_name("manage.py")


def system_needs_sudo() -> bool:
    return Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve() == Path("/") and os.geteuid() != 0


def inventory(system: bool) -> dict[str, dict]:
    if system and system_needs_sudo():
        result = subprocess.run(["sudo", "--", sys.executable, str(MANAGER), "uninstall",
                                 "--system", "--list", "--json"], check=True,
                                capture_output=True, text=True)
        return json.loads(result.stdout)
    bin_dir, registry_path, _ = paths(system)
    registry = read_registry(registry_path, "system" if system else "user", bin_dir)
    return registry_inventory(registry)


def remote_inventory(target: str, system: bool) -> dict[str, dict]:
    scope = "system" if system else "user"
    target = valid_target(target)
    recorded = cached(target, scope)
    scanned = scan_remote(target, scope)
    result = {}
    for module, entry in scanned.items():
        issues = list(entry["issues"])
        if module not in recorded:
            issues.append("not in local deployment registry")
        elif recorded[module]["components"] != entry["components"]:
            issues.append("local and remote component records differ")
        result[module] = {"components": entry["components"], "issues": issues}
    for module, entry in recorded.items():
        if module not in result:
            result[module] = {"components": entry["components"],
                              "issues": ["missing from remote portable registry"]}
    return result


def scope_for(module: str, inventories: dict[str, dict], system_only: bool) -> str:
    if system_only:
        if module in inventories.get("system", {}):
            return "system"
    else:
        for scope in ("user", "system"):
            if module in inventories.get(scope, {}):
                return scope
    raise RuntimeError(f"Module is not installed in the selected scope: {module}")


def scope_for_component(module: str, component: str, inventories: dict[str, dict],
                        system_only: bool) -> str:
    scopes = ("system",) if system_only else ("user", "system")
    for scope in scopes:
        details = inventories.get(scope, {}).get(module)
        if details and details["components"] is not None and component in details["components"]:
            return scope
    raise RuntimeError(f"Component is not installed in the selected scope: {module}:{component}")


def select_interactively(inventories: dict[str, dict]) -> dict[str, dict[str, set[str] | None]]:
    choices = [(scope, module) for scope in inventories for module in sorted(inventories[scope])]
    names = [f"{module} [{scope}]" for scope, module in choices]
    descriptions = {}
    for name, (scope, module) in zip(names, choices):
        issues = inventories[scope][module]["issues"]
        if issues:
            descriptions[name] = f"{len(issues)} installed file issue(s); review before changing files"
        elif module in MODULES:
            descriptions[name] = MODULES[module]["description"]
    selected = choose_categorized_modules(
        names, descriptions,
        {name: MODULES[module]["category"] if module in MODULES else "Other"
         for name, (_, module) in zip(names, choices)})
    result: dict[str, dict[str, set[str] | None]] = {scope: {} for scope in inventories}
    lookup = dict(zip(names, choices))
    for name in selected:
        scope, module = lookup[name]
        components = inventories[scope][module]["components"]
        if components is None:
            result[scope][module] = None
            continue
        labels = {item: MODULES[module]["components"][item]["description"] for item in components}
        chosen = choose_modules([], False, components, labels,
                                heading=f"{MODULES[module]['display_name']} installed sub-modules [{scope}]",
                                selection_label="sub-module")
        result[scope][module] = set(chosen)
    return result


def select_explicit(args: argparse.Namespace, inventories: dict[str, dict]) -> dict[str, dict[str, set[str] | None]]:
    result: dict[str, dict[str, set[str] | None]] = {scope: {} for scope in inventories}
    if args.all:
        if args.module or args.component:
            raise RuntimeError("--all cannot be combined with --module or --component")
        for scope, entries in inventories.items():
            result[scope] = {module: None for module in entries}
        return result
    for module in args.module:
        scope = scope_for(module, inventories, args.system)
        result[scope][module] = None
    for spec in args.component:
        module, separator, component = spec.partition(":")
        if not separator:
            raise RuntimeError(f"Use MODULE:NAME for --component: {spec}")
        scope = scope_for_component(module, component, inventories, args.system)
        if module not in result[scope]:
            result[scope][module] = {component}
        elif result[scope][module] is not None:
            result[scope][module].add(component)
    return result


def load_inventories(args: argparse.Namespace) -> dict[str, dict]:
    if args.system:
        inventories = {"system": remote_inventory(args.ssh, True) if args.ssh else inventory(True)}
    else:
        user = remote_inventory(args.ssh, False) if args.ssh else inventory(False)
        inventories = {"user": user}
        requested = [*args.module, *args.component]
        missing_user_module = any(module not in user for module in args.module)
        missing_user_component = any(
            spec.partition(":")[0] not in user or
            spec.partition(":")[2] not in (user[spec.partition(":")[0]]["components"] or [])
            for spec in args.component
        )
        if args.list or args.all or not requested or missing_user_module or missing_user_component:
            inventories["system"] = remote_inventory(args.ssh, True) if args.ssh else inventory(True)
    return inventories
