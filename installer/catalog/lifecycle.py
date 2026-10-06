"""Validate pre-remove and post-install lifecycle hooks."""

from __future__ import annotations

import re
from pathlib import Path


def lifecycle_definitions(module: str, manifest: Path, source: dict, commands: dict) -> dict:
    result = {}
    hook = source.get("pre_remove")
    if hook is not None:
        if (not isinstance(hook, dict) or hook.get("command") not in commands
                or not isinstance(hook.get("args"), list)
                or any(not isinstance(arg, str) for arg in hook["args"])):
            raise SystemExit(f"Invalid {module}.pre_remove in {manifest}")
        for field in ("system_arg", "purge_arg"):
            if field in hook and not isinstance(hook[field], str):
                raise SystemExit(f"Invalid {module}.pre_remove.{field} in {manifest}")
        if "root_env" in hook and (not isinstance(hook["root_env"], str)
                                   or not re.fullmatch(r"[A-Z][A-Z0-9_]*", hook["root_env"])):
            raise SystemExit(f"Invalid {module}.pre_remove.root_env in {manifest}")
        result["pre_remove"] = hook
    for field_name in ("post_install", "post_update"):
        hook = source.get(field_name)
        if hook is None:
            continue
        if (not isinstance(hook, dict) or hook.get("command") not in commands
                or not isinstance(hook.get("args"), list)
                or any(not isinstance(arg, str) for arg in hook["args"])):
            raise SystemExit(f"Invalid {module}.{field_name} in {manifest}")
        if not isinstance(hook.get("prompt"), str) or not hook["prompt"].strip():
            raise SystemExit(f"Invalid {module}.{field_name}.prompt in {manifest}")
        for field in ("system_arg", "root_env"):
            if field in hook and not isinstance(hook[field], str):
                raise SystemExit(f"Invalid {module}.{field_name}.{field} in {manifest}")
        if "root_env" in hook and not re.fullmatch(r"[A-Z][A-Z0-9_]*", hook["root_env"]):
            raise SystemExit(f"Invalid {module}.{field_name}.root_env in {manifest}")
        result[field_name] = hook
    return result
