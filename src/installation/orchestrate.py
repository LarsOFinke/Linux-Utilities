#!/usr/bin/env python3
"""Interactive root setup UI that delegates installation to each module."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from catalog import MODULES, choose_targets, installed_components, selection_options
from manage import paths, read_registry

REPOSITORY = Path(__file__).resolve().parents[2]
DESCRIPTIONS = {
    name: f"{definition['display_name']} [{definition['category']} / {definition['subcategory']}] — {definition['description']}"
    for name, definition in MODULES.items()
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", action="store_true", help="Install commands system-wide")
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
    args = parser.parse_args()
    try:
        available = sorted(MODULES)
        available_components = None
        if (not args.module and not args.component and not args.all) or args.list:
            bin_dir, registry_path, _ = paths(args.system)
            registry = read_registry(registry_path, "system" if args.system else "user", bin_dir)
            available_components = {
                module: set(definition["components"]) -
                (installed_components(module, registry["modules"][module])
                 if module in registry["modules"] else set())
                for module, definition in MODULES.items() if definition["components"]
            }
            available = [module for module in available if not MODULES[module]["components"]
                         or available_components[module]]
        if args.list:
            print("\n".join(selection_options(available, available_components)))
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
        command = [sys.executable, str(REPOSITORY / "src/installation/manage.py"), "install"]
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
        if not args.no_configure and sys.stdin.isatty():
            base = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")) if system else Path.home()
            bin_dir = base / ("usr/local/bin" if system else ".local/bin")
            for module in selected:
                if selection[module] is not None:
                    continue
                hook = MODULES[module].get("post_install")
                if not hook or input(f"{hook['prompt']} [y/N] ").strip() not in ("y", "Y"):
                    continue
                executable = bin_dir / hook["command"]
                environment = dict(os.environ)
                if hook.get("root_env"):
                    environment[hook["root_env"]] = str(base)
                command = [str(executable)]
                if system and hook.get("system_arg"):
                    command.append(hook["system_arg"])
                if system and os.geteuid() != 0 and test_root == Path("/"):
                    command = ["sudo", "--", *command]
                subprocess.run([*command, *hook["args"]], env=environment, check=True)
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Linux-Utilities setup: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
