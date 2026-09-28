#!/usr/bin/env python3
"""Interactive root setup UI that delegates installation to each module."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from manage import MODULES, choose_modules

REPOSITORY = Path(__file__).resolve().parents[2]
DESCRIPTIONS = {
    name: f"{definition['display_name']} [{definition['category']}] — {definition['description']}"
    for name, definition in MODULES.items()
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", action="store_true", help="Install commands system-wide")
    parser.add_argument("--module", action="append", default=[], choices=sorted(MODULES))
    parser.add_argument("--all", action="store_true", help="Set up all modules")
    parser.add_argument("--list", action="store_true", help="List available modules")
    parser.add_argument(
        "--no-configure",
        action="store_true",
        help="Skip optional module configuration prompts",
    )
    args = parser.parse_args()
    available = sorted(MODULES)
    if args.list:
        print("\n".join(available))
        return 0
    try:
        if not args.module and not args.all:
            print(f"Linux-Utilities setup — {'system-wide' if args.system else 'current user'}")
        selected = choose_modules(args.module, args.all, available, DESCRIPTIONS)
        system_only = [module for module in selected if MODULES[module].get("system_only")]
        if system_only and not args.system and len(system_only) != len(selected):
            raise RuntimeError("Selected modules require different install scopes; use --system or select each scope separately.")
        print(f"Selected modules: {', '.join(selected)}", flush=True)
        system = args.system or bool(system_only)
        command = [sys.executable, str(REPOSITORY / "src/installation/manage.py"), "install"]
        if system:
            command.append("--system")
        for module in selected:
            command.extend(("--module", module))
        test_root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
        if system_only and not args.system and os.geteuid() != 0 and test_root == Path("/"):
            command = ["sudo", "--", *command]
        subprocess.run(command, check=True)
        if not args.no_configure and sys.stdin.isatty():
            base = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")) if system else Path.home()
            bin_dir = base / ("usr/local/bin" if system else ".local/bin")
            for module in selected:
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
                subprocess.run([*command, *hook["args"]], env=environment, check=True)
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Linux-Utilities setup: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
