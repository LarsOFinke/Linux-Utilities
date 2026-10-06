"""Load the repository catalog and resolve each stable module ID."""

from __future__ import annotations

import json
import re

from catalog.manifest import load_manifest
from catalog.source import CATALOG_PATH, relative_path


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
        manifest = relative_path(reference, f"{module}.manifest")
        modules[module] = load_manifest(module, manifest)
    data["modules"] = modules
    return data
