"""Load installed ownership from local and SSH scopes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from core.registry import paths, read_registry, registry_inventory
from remote.deploy import scan_remote
from remote.state import cached, valid_target

MANAGER = Path(__file__).resolve().parents[1] / "main.py"


def system_needs_sudo() -> bool:
    return Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve() == Path("/") and os.geteuid() != 0


def inventory(system: bool) -> dict[str, dict]:
    if system and system_needs_sudo():
        result = subprocess.run(["sudo", "--", sys.executable, str(MANAGER), "uninstall",
                                 "--system", "--list", "--json"], check=True,
                                capture_output=True, text=True)
        return json.loads(result.stdout)
    bin_dir, registry_path, _ = paths(system)
    registry = read_registry(registry_path, "system" if system else "user", bin_dir)
    return registry_inventory(registry)


def remote_inventory(target: str, system: bool) -> dict[str, dict]:
    scope = "system" if system else "user"
    target = valid_target(target)
    recorded = cached(target, scope)
    scanned = scan_remote(target, scope)
    result = {}
    for module, entry in scanned.items():
        issues = list(entry["issues"])
        if module not in recorded:
            issues.append("not in local deployment registry")
        elif recorded[module]["components"] != entry["components"]:
            issues.append("local and remote component records differ")
        result[module] = {"components": entry["components"], "issues": issues}
    for module, entry in recorded.items():
        if module not in result:
            result[module] = {"components": entry["components"],
                              "issues": ["missing from remote portable registry"]}
    return result


def load_inventories(args: argparse.Namespace) -> dict[str, dict]:
    if args.system:
        inventories = {"system": remote_inventory(args.ssh, True) if args.ssh else inventory(True)}
    else:
        user = remote_inventory(args.ssh, False) if args.ssh else inventory(False)
        inventories = {"user": user}
        requested = [*args.module, *args.component]
        missing_user_module = any(module not in user for module in args.module)
        missing_user_component = any(
            spec.partition(":")[0] not in user or
            spec.partition(":")[2] not in (user[spec.partition(":")[0]]["components"] or [])
            for spec in args.component
        )
        if args.list or args.all or not requested or missing_user_module or missing_user_component:
            inventories["system"] = remote_inventory(args.ssh, True) if args.ssh else inventory(True)
    return inventories
