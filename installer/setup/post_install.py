"""Run optional configuration hooks after a successful local installation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from catalog import MODULES


def configure(selection: dict[str, set[str] | None], system: bool, test_root: Path,
              hook_name: str = "post_install") -> None:
    if not sys.stdin.isatty():
        return
    base = test_root if system else Path.home()
    bin_dir = base / ("usr/local/bin" if system else ".local/bin")
    for module, components in selection.items():
        if components is not None:
            continue
        hook = MODULES[module].get(hook_name)
        if not hook or input(f"{hook['prompt']} [y/N] ").strip() not in ("y", "Y"):
            continue
        environment = dict(os.environ)
        if hook.get("root_env"):
            environment[hook["root_env"]] = str(base)
        command = [str(bin_dir / hook["command"])]
        if system and hook.get("system_arg"):
            command.append(hook["system_arg"])
        if system and os.geteuid() != 0 and test_root == Path("/"):
            command = ["sudo", "--", *command]
        subprocess.run([*command, *hook["args"]], env=environment, check=True)
