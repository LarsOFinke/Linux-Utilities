"""Validate and build the standalone pre-removal hook."""

from __future__ import annotations

import os
from pathlib import Path

from .files import digest
from .state import fail


def hook_command(state: dict, system: bool, purge_config: bool, root: Path, manifest: dict) -> tuple[list[str], dict[str, str]] | None:
    hook = state.get("pre_remove") or manifest.get("pre_remove")
    if not hook:
        return None
    record = state["commands"][hook["command"]]
    executable = Path(record["path"])
    if not executable.is_file() or executable.is_symlink() or digest(executable) != record["sha256"]:
        fail(f"Cannot safely run module removal hook: {executable}")
    command = [str(executable)]
    if system and hook.get("system_arg"):
        command.append(hook["system_arg"])
    command.extend(hook["args"])
    if purge_config and hook.get("purge_arg"):
        command.append(hook["purge_arg"])
    environment = dict(os.environ)
    if hook.get("root_env"):
        environment[hook["root_env"]] = str(root)
    return command, environment
