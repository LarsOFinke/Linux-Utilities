"""Route installed module and component selections to their scopes."""

from __future__ import annotations

import argparse

from catalog import MODULES
from selection.available import choose_categorized_modules, choose_modules


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
    lookup = dict(zip(names, choices))
    chosen_components: dict[str, set[str] | None] = {}

    def resolve_modules(modules: list[str]) -> list[str]:
        resolved = {}
        for name in modules:
            scope, module = lookup[name]
            components = inventories[scope][module]["components"]
            if components is None:
                resolved[name] = None
                continue
            labels = {item: MODULES[module]["components"][item]["description"] for item in components}
            chosen = choose_modules([], False, components, labels,
                                    heading=f"{MODULES[module]['display_name']} installed sub-modules [{scope}]",
                                    selection_label="sub-module", allow_back=True)
            resolved[name] = set(chosen)
        chosen_components.update(resolved)
        return modules

    selected = choose_categorized_modules(
        names, descriptions,
        {name: MODULES[module]["category"] if module in MODULES else "Other"
         for name, (_, module) in zip(names, choices)}, resolve_modules)
    result: dict[str, dict[str, set[str] | None]] = {scope: {} for scope in inventories}
    for name in selected:
        scope, module = lookup[name]
        result[scope][module] = chosen_components[name]
    return result


def select_explicit(
    args: argparse.Namespace, inventories: dict[str, dict]
) -> dict[str, dict[str, set[str] | None]]:
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
