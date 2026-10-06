"""Run a verified module-owned removal hook before managed file deletion."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from catalog import MODULES
from core.files import sha256


def run_pre_remove_hook(module: str, entry: dict, system: bool, base: Path, purge_config: bool) -> None:
    hook = entry.get("pre_remove") or MODULES.get(module, {}).get("pre_remove")
    if not hook:
        return
    command = entry["commands"][hook["command"]]
    target = Path(command["path"])
    if not target.is_file() or target.is_symlink() or sha256(target) != command["sha256"]:
        raise RuntimeError(f"Cannot safely run {module} removal hook with a missing or changed command: {target}")
    hook_args = [str(target)]
    if system and hook.get("system_arg"):
        hook_args.append(hook["system_arg"])
    hook_args.extend(hook["args"])
    if purge_config and hook.get("purge_arg"):
        hook_args.append(hook["purge_arg"])
    environment = dict(os.environ)
    if hook.get("root_env"):
        environment[hook["root_env"]] = str(base)
    subprocess.run(hook_args, env=environment, check=True)
