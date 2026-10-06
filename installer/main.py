#!/usr/bin/env python3
"""Command entry point for shared install, update, and removal transactions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from catalog import MODULES, installed_components
from selection.available import choose_targets, selection_options
from core.registry import paths, read_registry, registry_inventory
from setup.build import build_commands
from setup.install import install
from uninstall.remove import uninstall
from update.refresh import update


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] in {"setup", "select-update", "select-uninstall"}:
        if arguments[0] == "setup":
            from setup.orchestrate import main as orchestrate
        elif arguments[0] == "select-update":
            from update.orchestrate import main as orchestrate
        else:
            from uninstall.orchestrate import main as orchestrate
        if arguments[0] == "select-uninstall":
            try:
                return orchestrate(arguments[1:])
            except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
                print(f"Linux-Utilities uninstall: {error}", file=sys.stderr)
                return 1
        return orchestrate(arguments[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "update", "uninstall"])
    parser.add_argument("--system", action="store_true", help="Use /usr/local/bin and the system registry")
    parser.add_argument("--module", action="append", default=[], help="Select a module by name; repeatable")
    parser.add_argument("--component", action="append", default=[], metavar="MODULE:NAME",
                        help="Select an independently managed component; repeatable")
    parser.add_argument("--all", action="store_true", help="Select all available modules")
    parser.add_argument("--list", action="store_true", help="List available or installed modules")
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--force", action="store_true", help="Remove locally modified installed commands")
    parser.add_argument("--purge-config", action="store_true", help="Also delete privacy runtime configuration")
    args = parser.parse_args(arguments)
    bin_dir, registry_path, base = paths(args.system)
    registry = read_registry(registry_path, "system" if args.system else "user", bin_dir)
    available = sorted(MODULES if args.action == "install" else registry["modules"])
    available_components = (None if args.action == "install" else
                            {module: installed_components(module, registry["modules"][module])
                             for module in available if module in MODULES and MODULES[module]["components"]})
    if args.list:
        if args.json:
            print(json.dumps(registry_inventory(registry) if args.action in ("uninstall", "update") else {}))
            return 0
        print("\n".join(selection_options(available, available_components)))
        return 0
    if not available:
        raise RuntimeError("No installed modules are recorded.")
    selection = choose_targets(args.module, args.component, args.all, available,
                               available_components=available_components)
    selected = list(selection)
    if args.action == "install":
        with tempfile.TemporaryDirectory(prefix="linux-utilities-build-") as directory:
            built = build_commands(selected, Path(directory), selection)
            install(selected, registry, bin_dir, registry_path, args.system, built, selection)
    elif args.action == "update":
        update(selected, bin_dir, registry_path, args.system, selection)
    else:
        uninstall(selected, registry, registry_path, args.system, base, args.force, args.purge_config, selection)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Linux-Utilities setup: {error}", file=sys.stderr)
        sys.exit(1)
