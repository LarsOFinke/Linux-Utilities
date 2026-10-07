"""Interactive and explicit module/component selection."""

from __future__ import annotations

import sys
from collections.abc import Callable

from catalog import MODULES


class BackSelection(Exception):
    """Return to the preceding interactive menu."""


def selection_options(available: list[str],
                      available_components: dict[str, set[str]] | None = None) -> list[str]:
    """List valid component selections for the current install state."""
    options = []
    for module in available:
        defined = MODULES.get(module, {}).get("components", {})
        if defined:
            names = (defined if available_components is None else
                     (name for name in defined if name in available_components.get(module, set())))
            options.extend(f"{module}:{name}" for name in names)
        else:
            options.append(module)
    return options


def choose_categorized_modules(available: list[str], descriptions: dict[str, str] | None,
                               categories: dict[str, str],
                               resolve_modules: Callable[[list[str]], list[str]] | None = None) -> list[str]:
    """Ask for concerns first, then modules within each chosen concern."""
    category_names = sorted({categories[name] for name in available})
    while True:
        selected_categories = choose_modules([], False, category_names, heading="Categories",
                                              selection_label="category", allow_back=True)
        selected = []
        try:
            for category in selected_categories:
                names = [name for name in available if categories[name] == category]
                while True:
                    modules = choose_modules([], False, names, descriptions,
                                             heading=f"{category} modules", allow_back=True)
                    try:
                        selected.extend(resolve_modules(modules) if resolve_modules else modules)
                    except BackSelection:
                        continue
                    break
        except BackSelection:
            continue
        return selected


def choose_targets(requested_modules: list[str], requested_components: list[str],
                   all_modules: bool, available: list[str],
                   descriptions: dict[str, str] | None = None,
                   available_components: dict[str, set[str]] | None = None) -> dict[str, set[str] | None]:
    """Return modules selected in full (None) or selected component names."""
    options = selection_options(available, available_components)
    if all_modules and (requested_modules or requested_components):
        raise RuntimeError("--all cannot be combined with --module or --component")
    for spec in requested_components:
        if spec not in options or ":" not in spec:
            raise RuntimeError(f"Unknown or uninstalled component: {spec}")
    if all_modules:
        chosen = available
    elif requested_modules or requested_components:
        chosen = [*requested_modules, *requested_components]
        unknown = set(requested_modules) - set(available)
        if unknown:
            raise RuntimeError(f"Unknown or uninstalled module: {', '.join(sorted(unknown))}")
    else:
        def resolve_modules(modules: list[str]) -> list[str]:
            resolved = []
            for module in modules:
                definitions = MODULES.get(module, {}).get("components", {})
                if not definitions:
                    resolved.append(module)
                    continue
                names = [name for name in definitions if f"{module}:{name}" in options]
                labels = {name: definitions[name]["description"] for name in names}
                selected_names = choose_modules([], False, names, labels,
                                                heading=f"{MODULES[module]['display_name']} sub-modules",
                                                selection_label="sub-module", allow_back=True)
                resolved.extend(f"{module}:{name}" for name in selected_names)
            return resolved

        chosen = choose_categorized_modules(
            available, descriptions, {name: MODULES[name]["category"] for name in available},
            resolve_modules)
    selection: dict[str, set[str] | None] = {}
    for item in chosen:
        module, sep, name = item.partition(":")
        if not sep:
            selection[module] = None
        elif module not in selection:
            selection[module] = {name}
        elif selection[module] is not None:
            selection[module].add(name)
    return selection


def choose_modules(
    requested: list[str],
    all_modules: bool,
    available: list[str],
    descriptions: dict[str, str] | None = None,
    heading: str = "Modules",
    selection_label: str = "module",
    allow_back: bool = False,
) -> list[str]:
    if all_modules:
        return available
    if requested:
        unknown = set(requested) - set(available)
        if unknown:
            raise RuntimeError(f"Unknown or uninstalled module: {', '.join(sorted(unknown))}")
        return list(dict.fromkeys(requested))
    if not sys.stdin.isatty():
        raise RuntimeError("Choose modules with --module NAME or --all.")
    print(f"{heading}:")
    for index, name in enumerate(available, 1):
        description = f" — {descriptions[name]}" if descriptions and name in descriptions else ""
        print(f"  {index}. {name}{description}")
    while True:
        try:
            suffix = ", 'b' to go back" if allow_back else ""
            answer = input(f"Select {selection_label} numbers separated by commas, 'all', or 'q'{suffix}: ").strip().lower()
        except EOFError as error:
            raise RuntimeError("Selection cancelled.") from error
        if answer == "all":
            return available
        if allow_back and answer in {"b", "back"}:
            raise BackSelection
        if answer.lower() in {"q", "quit"}:
            raise RuntimeError("Selection cancelled.")
        try:
            indices = [int(piece.strip()) for piece in answer.split(",")]
            if any(index < 1 or index > len(available) for index in indices):
                raise ValueError("Module number is out of range")
            selected = [available[index - 1] for index in indices]
        except (ValueError, IndexError):
            print("Enter listed numbers, 'all', 'b', or 'q'." if allow_back
                  else "Enter listed numbers, 'all', or 'q'.")
            continue
        return list(dict.fromkeys(selected))
