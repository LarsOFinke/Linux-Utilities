"""Local records for successful remote portable deployments."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from catalog import MODULES
from core.registry import atomic_json, paths, read_registry, registry_lock


def valid_target(target: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", target) or target.count("@") > 1:
        raise RuntimeError(f"Invalid SSH target: {target!r}")
    return target


def local_registry() -> tuple[dict, Path]:
    bin_dir, path, _ = paths(False)
    return read_registry(path, "user", bin_dir), path


def cached(target: str, scope: str) -> dict:
    registry, _ = local_registry()
    return registry.get("remote_deployments", {}).get(valid_target(target), {}).get(scope, {})


def record(target: str, scope: str, module: str, components: set[str] | None, action: str) -> None:
    with registry_lock(paths(False)[1]):
        registry, path = local_registry()
        deployments = registry.setdefault("remote_deployments", {})
        scopes = deployments.setdefault(target, {})
        entries = scopes.setdefault(scope, {})
        if action in ("install", "update"):
            names = set(MODULES[module]["components"]) if components is None else components
            previous = entries.get(module, {}).get("components", [])
            entries[module] = {
                "components": sorted(set(previous) | names) if MODULES[module]["components"] else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        elif module in entries:
            if components is None or not MODULES[module]["components"]:
                del entries[module]
            else:
                remaining = set(entries[module]["components"] or []) - components
                if remaining:
                    entries[module]["components"] = sorted(remaining)
                else:
                    del entries[module]
        if not entries:
            del scopes[scope]
        if not scopes:
            del deployments[target]
        registry["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(path, registry)
