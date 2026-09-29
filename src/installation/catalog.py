"""Validate module manifests and select modules for installation."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY / "configuration/install.json"


def relative_path(value: str, label: str) -> Path:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[a-zA-Z0-9_./-]+", value)
        or Path(value).is_absolute()
        or ".." in Path(value).parts
        or Path(value) == Path(".")
    ):
        raise SystemExit(f"Invalid {label} in {CATALOG_PATH}: {value!r}")
    return Path(value)


def load_catalog() -> dict:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read installation catalog {CATALOG_PATH}: {error}") from error
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise SystemExit(f"Unsupported installation catalog: {CATALOG_PATH}")
    scopes = data.get("scopes")
    references = data.get("modules")
    if not isinstance(scopes, dict) or not isinstance(references, dict) or not references:
        raise SystemExit(f"Invalid scopes or modules in {CATALOG_PATH}")
    for scope in ("user", "system"):
        definition = scopes.get(scope)
        if not isinstance(definition, dict):
            raise SystemExit(f"Missing {scope} scope in {CATALOG_PATH}")
        for field in ("bin_dir", "registry"):
            relative_path(definition.get(field), f"{scope}.{field}")

    modules = {}
    for module, reference in references.items():
        if not isinstance(module, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", module):
            raise SystemExit(f"Invalid module name in {CATALOG_PATH}: {module!r}")
        manifest_relative = relative_path(reference, f"{module}.manifest")
        manifest_path = REPOSITORY / manifest_relative
        try:
            source = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"Cannot read module manifest {manifest_path}: {error}") from error
        if not isinstance(source, dict) or source.get("schema_version") != 1 or source.get("id") != module:
            raise SystemExit(f"Invalid module manifest: {manifest_path}")
        for field in ("display_name", "category", "subcategory", "description"):
            value = source.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                raise SystemExit(f"Invalid {module}.{field} in {manifest_path}")
        supported_scopes = source.get("scopes")
        if (not isinstance(supported_scopes, list) or not supported_scopes or
                any(not isinstance(scope, str) or scope not in ("user", "system") for scope in supported_scopes) or
                len(set(supported_scopes)) != len(supported_scopes)):
            raise SystemExit(f"Invalid {module}.scopes in {manifest_path}")
        def source_path(value: str, label: str) -> str:
            return str(manifest_relative.parent / relative_path(value, label))

        definition = {key: source[key] for key in ("display_name", "category", "subcategory", "description")}
        definition["scopes"] = supported_scopes
        definition["system_only"] = "user" not in supported_scopes
        definition["manifest"] = str(manifest_relative)
        for field in ("setup", "documentation"):
            definition[field] = source_path(source.get(field), f"{module}.{field}")
        commands = source.get("commands")
        if not isinstance(commands, dict) or not commands:
            raise SystemExit(f"Invalid {module}.commands in {manifest_path}")
        definition["commands"] = {}
        for name, path in commands.items():
            if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
                raise SystemExit(f"Invalid command name: {name!r}")
            definition["commands"][name] = source_path(path, f"{module}.commands.{name}")
        helpers = source.get("non_executable_commands", [])
        if not isinstance(helpers, list) or any(name not in commands for name in helpers):
            raise SystemExit(f"Invalid {module}.non_executable_commands in {manifest_path}")
        definition["non_executable_commands"] = helpers
        components = source.get("components", {})
        if not isinstance(components, dict):
            raise SystemExit(f"Invalid {module}.components in {manifest_path}")
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
                raise SystemExit(f"Invalid {module}.components.{name} in {manifest_path}")
            overlap = claimed.intersection(component["commands"])
            if overlap:
                raise SystemExit(f"Commands shared by {module} components: {', '.join(sorted(overlap))}")
            claimed.update(component["commands"])
        if components and (claimed != set(commands) or source.get("pre_remove") or source.get("post_install")
                           or source.get("system_cron")):
            raise SystemExit(f"{module} components must partition commands and have no module lifecycle hooks or cron")
        definition["components"] = components
        for field in ("examples", "cron_templates"):
            items = source.get(field)
            if not isinstance(items, list):
                raise SystemExit(f"Invalid {module}.{field} in {manifest_path}")
            definition[field] = [source_path(item, f"{module}.{field}") for item in items]
        cron = source.get("system_cron")
        if cron is not None:
            if not isinstance(cron, dict) or not isinstance(cron.get("name"), str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", cron["name"]):
                raise SystemExit(f"Invalid {module}.system_cron in {manifest_path}")
            definition["system_cron"] = {"name": cron["name"], "source": source_path(cron.get("source"), f"{module}.system_cron.source")}
        builds = source.get("build_commands", {})
        if not isinstance(builds, dict) or any(name not in commands for name in builds):
            raise SystemExit(f"Invalid {module}.build_commands in {manifest_path}")
        definition["build_commands"] = {name: source_path(script, f"{module}.build_commands.{name}") for name, script in builds.items()}
        hook = source.get("pre_remove")
        if hook is not None:
            if not isinstance(hook, dict) or hook.get("command") not in commands or not isinstance(hook.get("args"), list) or any(not isinstance(arg, str) for arg in hook["args"]):
                raise SystemExit(f"Invalid {module}.pre_remove in {manifest_path}")
            for field in ("system_arg", "purge_arg"):
                if field in hook and not isinstance(hook[field], str):
                    raise SystemExit(f"Invalid {module}.pre_remove.{field} in {manifest_path}")
            if "root_env" in hook and (not isinstance(hook["root_env"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", hook["root_env"])):
                raise SystemExit(f"Invalid {module}.pre_remove.root_env in {manifest_path}")
            definition["pre_remove"] = hook
        post_install = source.get("post_install")
        if post_install is not None:
            if not isinstance(post_install, dict) or post_install.get("command") not in commands or not isinstance(post_install.get("args"), list) or any(not isinstance(arg, str) for arg in post_install["args"]):
                raise SystemExit(f"Invalid {module}.post_install in {manifest_path}")
            if not isinstance(post_install.get("prompt"), str) or not post_install["prompt"].strip():
                raise SystemExit(f"Invalid {module}.post_install.prompt in {manifest_path}")
            for field in ("system_arg", "root_env"):
                if field in post_install and not isinstance(post_install[field], str):
                    raise SystemExit(f"Invalid {module}.post_install.{field} in {manifest_path}")
            if "root_env" in post_install and not re.fullmatch(r"[A-Z][A-Z0-9_]*", post_install["root_env"]):
                raise SystemExit(f"Invalid {module}.post_install.root_env in {manifest_path}")
            definition["post_install"] = post_install
        for field in ("runtime_configs", "schedules"):
            scoped = source.get(field, {})
            if not isinstance(scoped, dict) or any(key not in ("user", "system") for key in scoped):
                raise SystemExit(f"Invalid {module}.{field} in {manifest_path}")
            for scope, items in scoped.items():
                if not isinstance(items, list):
                    raise SystemExit(f"Invalid {module}.{field}.{scope} in {manifest_path}")
                for item in items:
                    if field == "schedules" and scope == "user" and isinstance(item, str) and item.startswith("user crontab: ") and "\n" not in item:
                        continue
                    relative_path(item, f"{module}.{field}.{scope}")
            definition[field] = scoped
        modules[module] = definition
    data["modules"] = modules
    return data


CATALOG = load_catalog()
MODULES = CATALOG["modules"]


def component_commands(module: str, names: set[str]) -> set[str]:
    definition = MODULES[module]
    unknown = names - definition["components"].keys()
    if unknown:
        raise RuntimeError(f"Unknown component for {module}: {', '.join(sorted(unknown))}")
    return {command for name in names for command in definition["components"][name]["commands"]}


def installed_components(module: str, entry: dict) -> set[str]:
    """Infer ownership for registries written before components existed."""
    definitions = MODULES[module]["components"]
    if not definitions:
        return set()
    recorded = entry.get("components")
    if recorded is not None:
        names = set(recorded)
        component_commands(module, names)
        if set(entry["commands"]) != component_commands(module, names):
            raise RuntimeError(f"Inconsistent component registry for {module}")
        return names
    owned = set(entry["commands"])
    names = {name for name, item in definitions.items() if owned.intersection(item["commands"])}
    if owned != component_commands(module, names):
        raise RuntimeError(f"Cannot infer components from legacy registry for {module}")
    return names


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
                               categories: dict[str, str]) -> list[str]:
    """Ask for concerns first, then modules within each chosen concern."""
    category_names = sorted({categories[name] for name in available})
    selected_categories = choose_modules([], False, category_names, heading="Categories",
                                          selection_label="category")
    selected = []
    for category in selected_categories:
        names = [name for name in available if categories[name] == category]
        selected.extend(choose_modules([], False, names, descriptions,
                                       heading=f"{category} modules"))
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
        chosen = []
        selected_modules = choose_categorized_modules(
            available, descriptions, {name: MODULES[name]["category"] for name in available})
        for module in selected_modules:
            definitions = MODULES.get(module, {}).get("components", {})
            if not definitions:
                chosen.append(module)
                continue
            names = [name for name in definitions if f"{module}:{name}" in options]
            labels = {name: definitions[name]["description"] for name in names}
            selected_names = choose_modules([], False, names, labels,
                                            heading=f"{MODULES[module]['display_name']} sub-modules",
                                            selection_label="sub-module")
            chosen.extend(f"{module}:{name}" for name in selected_names)
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
            answer = input(f"Select {selection_label} numbers separated by commas, 'all', or 'q': ").strip()
        except EOFError as error:
            raise RuntimeError("Selection cancelled.") from error
        if answer == "all":
            return available
        if answer.lower() in {"q", "quit"}:
            raise RuntimeError("Selection cancelled.")
        try:
            indices = [int(piece.strip()) for piece in answer.split(",")]
            if any(index < 1 or index > len(available) for index in indices):
                raise ValueError("Module number is out of range")
            selected = [available[index - 1] for index in indices]
        except (ValueError, IndexError):
            print("Enter listed numbers, 'all', or 'q'.")
            continue
        return list(dict.fromkeys(selected))
