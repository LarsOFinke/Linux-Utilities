#!/usr/bin/env python3
"""Select registered modules across user and system scopes for removal."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from catalog import MODULES
from remote.deploy import deploy
from selection.installed import select_explicit, select_interactively
from selection.inventory import load_inventories, system_needs_sudo

MANAGER = Path(__file__).resolve().parents[1] / "main.py"


def remove(selection: dict[str, dict[str, set[str] | None]], args: argparse.Namespace) -> None:
    for scope, modules in selection.items():
        if not modules:
            continue
        if args.ssh:
            deploy(args.ssh, modules, scope == "system", "uninstall", args.force)
            continue
        command = [sys.executable, str(MANAGER), "uninstall"]
        if scope == "system":
            command.append("--system")
        if args.force:
            command.append("--force")
        if args.purge_config:
            command.append("--purge-config")
        for module, components in modules.items():
            if components is None:
                command.extend(("--module", module))
            else:
                for name in sorted(components):
                    command.extend(("--component", f"{module}:{name}"))
        if scope == "system" and system_needs_sudo():
            command = ["sudo", "--", *command]
        subprocess.run(command, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", action="store_true", help="Show only system installations")
    parser.add_argument("--ssh", metavar="TARGET", help="Remove modules from an SSH target")
    parser.add_argument("--module", action="append", default=[], help="Remove an installed module")
    parser.add_argument("--component", action="append", default=[], metavar="MODULE:NAME")
    parser.add_argument("--all", action="store_true", help="Remove all installed modules in selected scopes")
    parser.add_argument("--list", action="store_true", help="List registered modules in selected scopes")
    parser.add_argument("--force", action="store_true", help="Remove locally modified commands")
    parser.add_argument("--purge-config", action="store_true", help="Purge supported runtime configuration")
    args = parser.parse_args(argv)
    inventories = load_inventories(args)
    if args.list:
        groups = sorted({MODULES[module]["category"] if module in MODULES else "Other"
                         for entries in inventories.values() for module in entries})
        for category in groups:
            print(f"{category}:")
            for scope, entries in inventories.items():
                for module, details in sorted(entries.items()):
                    if (MODULES[module]["category"] if module in MODULES else "Other") != category:
                        continue
                    print(f"  {module} [{scope}]")
                    if details["components"] is not None:
                        for component in details["components"]:
                            print(f"    {module}:{component}")
                    for issue in details["issues"]:
                        print(f"    warning: {issue}")
        return 0
    if not any(inventories.values()):
        raise RuntimeError("No installed modules are recorded.")
    selection = (select_explicit(args, inventories) if args.module or args.component or args.all
                 else select_interactively(inventories))
    remove(selection, args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Linux-Utilities uninstall: {error}", file=sys.stderr)
        sys.exit(1)
