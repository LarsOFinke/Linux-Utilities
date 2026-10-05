#!/usr/bin/env python3
"""Select installed modules and refresh their managed commands from this checkout."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from catalog import MODULES
from remote_deploy import deploy
from installed_selection import load_inventories, select_explicit, select_interactively, system_needs_sudo

MANAGER = Path(__file__).with_name("manage.py")


def apply_updates(selection: dict[str, dict[str, set[str] | None]], args: argparse.Namespace) -> None:
    for scope, modules in selection.items():
        if not modules:
            continue
        if args.ssh:
            deploy(args.ssh, modules, scope == "system", "update")
            continue
        command = [sys.executable, str(MANAGER), "update"]
        if scope == "system":
            command.append("--system")
        for module, components in modules.items():
            if components is None:
                command.extend(("--module", module))
            else:
                for name in sorted(components):
                    command.extend(("--component", f"{module}:{name}"))
        if scope == "system" and system_needs_sudo():
            command = ["sudo", "--", *command]
        subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", action="store_true", help="Update only system-scope installations")
    parser.add_argument("--ssh", metavar="TARGET", help="Update installed modules on an SSH target")
    parser.add_argument("--module", action="append", default=[], help="Update an installed module")
    parser.add_argument("--component", action="append", default=[], metavar="MODULE:NAME",
                        help="Update an installed component; repeatable")
    parser.add_argument("--all", action="store_true", help="Update all recorded modules in selected scopes")
    parser.add_argument("--list", action="store_true", help="List modules available to update")
    args = parser.parse_args()
    try:
        inventories = load_inventories(args)
        if args.list:
            for scope, entries in inventories.items():
                print(f"{scope}:")
                for module, details in sorted(entries.items()):
                    suffix = f" — {', '.join(details['components'])}" if details["components"] else ""
                    print(f"  {module}{suffix}")
                    if details.get("updates"):
                        print(f"    source changes: {', '.join(details['updates'])}")
                    for issue in details["issues"]:
                        print(f"    warning: {issue}")
            return 0
        if not any(inventories.values()):
            raise RuntimeError("No installed modules are recorded in the selected scope.")
        selection = (select_explicit(args, inventories)
                     if args.module or args.component or args.all
                     else select_interactively(inventories))
        if not any(selection.values()):
            raise RuntimeError("No modules selected for update.")
        for scope, modules in selection.items():
            for module, components in modules.items():
                if module not in MODULES:
                    raise RuntimeError(f"Module is no longer available in this checkout: {module}")
                installed = inventories[scope][module]["components"]
                if components is None and installed is not None:
                    modules[module] = set(installed)
        apply_updates(selection, args)
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Linux-Utilities update: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
