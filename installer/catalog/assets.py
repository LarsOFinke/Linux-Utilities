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
