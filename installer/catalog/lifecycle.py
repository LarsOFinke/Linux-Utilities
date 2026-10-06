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
    post_install = source.get("post_install")
    if post_install is not None:
        if (not isinstance(post_install, dict) or post_install.get("command") not in commands
                or not isinstance(post_install.get("args"), list)
                or any(not isinstance(arg, str) for arg in post_install["args"])):
            raise SystemExit(f"Invalid {module}.post_install in {manifest}")
        if not isinstance(post_install.get("prompt"), str) or not post_install["prompt"].strip():
            raise SystemExit(f"Invalid {module}.post_install.prompt in {manifest}")
        for field in ("system_arg", "root_env"):
            if field in post_install and not isinstance(post_install[field], str):
                raise SystemExit(f"Invalid {module}.post_install.{field} in {manifest}")
        if "root_env" in post_install and not re.fullmatch(r"[A-Z][A-Z0-9_]*", post_install["root_env"]):
            raise SystemExit(f"Invalid {module}.post_install.root_env in {manifest}")
        result["post_install"] = post_install
    return result
