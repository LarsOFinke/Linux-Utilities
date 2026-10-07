#!/usr/bin/env python3
"""Interactive root setup UI that delegates installation to each module."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from catalog import MODULES, REPOSITORY, installed_components
from selection.available import BackSelection, choose_targets
from core.registry import paths, read_registry
from remote.deploy import deploy, scan_remote
from setup.post_install import configure

DESCRIPTIONS = {
    name: f"{definition['display_name']} [{definition['subcategory']}] — {definition['description']}"
    for name, definition in MODULES.items()
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", action="store_true", help="Install commands system-wide")
    parser.add_argument("--ssh", metavar="TARGET", help="Install on an SSH target with portable module setup")
    parser.add_argument("--module", action="append", default=[], choices=sorted(MODULES))
    parser.add_argument("--component", action="append", default=[], metavar="MODULE:NAME",
                        help="Install one component of a module; repeatable")
    parser.add_argument("--all", action="store_true", help="Set up all modules")
    parser.add_argument("--list", action="store_true", help="List available modules")
    parser.add_argument(
        "--no-configure",
        action="store_true",
        help="Skip optional module configuration prompts",
    )
    args = parser.parse_args(argv)
    try:
        available = sorted(MODULES)
        available_components = None
        if (not args.module and not args.component and not args.all) or args.list:
            if args.ssh:
                installed = scan_remote(args.ssh, "system" if args.system else "user")
                installed_components_by_module = {
                    module: set(entry.get("components") or []) for module, entry in installed.items()
                }
            else:
                bin_dir, registry_path, _ = paths(args.system)
                registry = read_registry(registry_path, "system" if args.system else "user", bin_dir)
                installed_components_by_module = {
                    module: installed_components(module, registry["modules"][module])
                    for module in MODULES if module in registry["modules"] and MODULES[module]["components"]
                }
            available_components = {
                module: set(definition["components"]) - installed_components_by_module.get(module, set())
                for module, definition in MODULES.items() if definition["components"]
            }
            available = [module for module in available if not MODULES[module]["components"]
                         or available_components[module]]
        if args.list:
            for category in sorted({MODULES[module]["category"] for module in available}):
                print(f"{category}:")
                for module in available:
                    if MODULES[module]["category"] != category:
                        continue
                    print(f"  {module} — {MODULES[module]['subcategory']}")
                    for component in MODULES[module]["components"]:
                        if available_components is None or component in available_components[module]:
                            print(f"    {module}:{component}")
            return 0
        if not args.module and not args.component and not args.all:
            print(f"Linux-Utilities setup — {'system-wide' if args.system else 'current user'}")
        selection = choose_targets(args.module, args.component, args.all, available, DESCRIPTIONS,
                                   available_components)
        selected = list(selection)
        system_only = [module for module in selected if MODULES[module].get("system_only")]
        if system_only and not args.system and len(system_only) != len(selected):
            raise RuntimeError("Selected modules require different install scopes; use --system or select each scope separately.")
        print(f"Selected: {', '.join(module if names is None else ', '.join(f'{module}:{name}' for name in sorted(names)) for module, names in selection.items())}", flush=True)
        system = args.system or bool(system_only)
        if args.ssh:
            deploy(args.ssh, selection, system)
            return 0
        command = [sys.executable, str(REPOSITORY / "installer/main.py"), "install"]
        if system:
            command.append("--system")
        for module, names in selection.items():
            if names is None:
                command.extend(("--module", module))
            else:
                for name in sorted(names):
                    command.extend(("--component", f"{module}:{name}"))
        test_root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
        if system_only and not args.system and os.geteuid() != 0 and test_root == Path("/"):
            command = ["sudo", "--", *command]
        subprocess.run(command, check=True)
        if not args.no_configure:
            configure(selection, system, test_root)
        return 0
    except BackSelection:
        return 3
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Linux-Utilities setup: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
