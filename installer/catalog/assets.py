"""Validate examples, cron files, builds, and scoped runtime metadata."""

from __future__ import annotations

import re
from pathlib import Path

from catalog.source import relative_path, source_path


def asset_definitions(module: str, manifest: Path, source: dict, commands: dict) -> dict:
    result = {}
    for field in ("examples", "cron_templates"):
        items = source.get(field)
        if not isinstance(items, list):
            raise SystemExit(f"Invalid {module}.{field} in {manifest}")
        result[field] = [source_path(manifest, item, f"{module}.{field}") for item in items]
    cron = source.get("system_cron")
    if cron is not None:
        if (not isinstance(cron, dict) or not isinstance(cron.get("name"), str)
                or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", cron["name"])):
            raise SystemExit(f"Invalid {module}.system_cron in {manifest}")
        result["system_cron"] = {
            "name": cron["name"],
            "source": source_path(manifest, cron.get("source"), f"{module}.system_cron.source"),
        }
    builds = source.get("build_commands", {})
    if not isinstance(builds, dict) or any(name not in commands for name in builds):
        raise SystemExit(f"Invalid {module}.build_commands in {manifest}")
    result["build_commands"] = {
        name: source_path(manifest, script, f"{module}.build_commands.{name}")
        for name, script in builds.items()
    }
    bundles = source.get("bundle_commands", [])
    non_executable = set(source.get("non_executable_commands", []))
    if (not isinstance(bundles, list)
            or any(not isinstance(name, str) or name not in commands or name in non_executable
                   for name in bundles)
            or len(set(bundles)) != len(bundles)):
        raise SystemExit(f"Invalid {module}.bundle_commands in {manifest}")
    result["bundle_commands"] = bundles
    files = source.get("bundle_files", {})
    if (not isinstance(files, dict) or any(
            not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name)
            or name in commands for name in files)):
        raise SystemExit(f"Invalid {module}.bundle_files in {manifest}")
    result["bundle_files"] = {
        name: source_path(manifest, script, f"{module}.bundle_files.{name}")
        for name, script in files.items()
    }
    for component, item in source.get("components", {}).items():
        embedded = item.get("bundle_files", [])
        if (not isinstance(embedded, list)
                or any(not isinstance(name, str) or name not in files for name in embedded)
                or len(set(embedded)) != len(embedded)):
            raise SystemExit(f"Invalid {module}.components.{component}.bundle_files in {manifest}")
    for field in ("runtime_configs", "schedules"):
        scoped = source.get(field, {})
        if not isinstance(scoped, dict) or any(key not in ("user", "system") for key in scoped):
            raise SystemExit(f"Invalid {module}.{field} in {manifest}")
        for scope, items in scoped.items():
            if not isinstance(items, list):
                raise SystemExit(f"Invalid {module}.{field}.{scope} in {manifest}")
            for item in items:
                if (field == "schedules" and scope == "user" and isinstance(item, str)
                        and item.startswith("user crontab: ") and "\n" not in item):
                    continue
                relative_path(item, f"{module}.{field}.{scope}")
        result[field] = scoped
    return result
