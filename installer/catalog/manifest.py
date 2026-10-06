"""Read a module manifest and assemble its validated definition."""

from __future__ import annotations

import json
from pathlib import Path

from catalog.assets import asset_definitions
from catalog.commands import command_definitions
from catalog.lifecycle import lifecycle_definitions
from catalog.source import REPOSITORY, source_path


def load_manifest(module: str, relative: Path) -> dict:
    manifest = REPOSITORY / relative
    try:
        source = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read module manifest {manifest}: {error}") from error
    if not isinstance(source, dict) or source.get("schema_version") != 1 or source.get("id") != module:
        raise SystemExit(f"Invalid module manifest: {manifest}")
    for field in ("display_name", "category", "subcategory", "description"):
        value = source.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 120:
            raise SystemExit(f"Invalid {module}.{field} in {manifest}")
    scopes = source.get("scopes")
    if (not isinstance(scopes, list) or not scopes or
            any(not isinstance(scope, str) or scope not in ("user", "system") for scope in scopes) or
            len(set(scopes)) != len(scopes)):
        raise SystemExit(f"Invalid {module}.scopes in {manifest}")
    result = {key: source[key] for key in ("display_name", "category", "subcategory", "description")}
    result.update(scopes=scopes, system_only="user" not in scopes, manifest=str(relative))
    for field in ("setup", "documentation"):
        result[field] = source_path(relative, source.get(field), f"{module}.{field}")
    result.update(command_definitions(module, relative, source))
    result.update(asset_definitions(module, relative, source, result["commands"]))
    result.update(lifecycle_definitions(module, relative, source, result["commands"]))
    return result
