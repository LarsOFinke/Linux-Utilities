#!/usr/bin/env python3
"""Portable module installer, bundled with a module only for SSH deployment."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))
from portable_support import install as install_logic, uninstall as uninstall_logic
from portable_support.state import (component_commands as _component_commands,
                                    installed_components as _installed_components,
                                    locations as _locations, read_state as _read_state,
                                    registry_lock, fail)

MODULE = PACKAGE
MANIFEST: dict = {}
NAME = "module"


def configure(module_dir: Path) -> None:
    """Select the module whose manifest and files this helper manages."""
    global MODULE, MANIFEST, NAME
    MODULE = module_dir.resolve()
    MANIFEST = json.loads((MODULE / "module.json").read_text(encoding="utf-8"))
    NAME = MANIFEST["id"]

def locations(system: bool) -> tuple[Path, Path, Path]:
    return _locations(system, NAME)

def read_state(path: Path, system: bool) -> dict:
    return _read_state(path, system, NAME)

def component_commands(names: set[str]) -> set[str]:
    return _component_commands(names, MANIFEST)

def installed_components(state: dict) -> set[str]:
    return _installed_components(state, MANIFEST)

def install(bin_dir: Path, state_path: Path, root: Path, system: bool,
            selected: set[str] | None = None) -> None:
    install_logic.install(bin_dir, state_path, root, system, selected,
                          module=MODULE, manifest=MANIFEST, module_id=NAME)

def uninstall(state_path: Path, state: dict, system: bool, force: bool,
              purge_config: bool, root: Path, selected: set[str] | None = None) -> None:
    uninstall_logic.uninstall(state_path, state, system, force, purge_config, root, selected,
                              manifest=MANIFEST, module_id=NAME)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "update", "uninstall"))
    parser.add_argument("--module-dir", type=Path, default=PACKAGE, help=argparse.SUPPRESS)
    parser.add_argument("--system", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--purge-config", action="store_true")
    parser.add_argument("--no-configure", action="store_true")
    parser.add_argument("--component", action="append", default=[], metavar="NAME")
    args = parser.parse_args()
    configure(args.module_dir)
    system = args.system or "user" not in MANIFEST["scopes"]
    scope = "system" if system else "user"
    if scope not in MANIFEST["scopes"]:
        fail(f"{NAME} does not support {scope} installation")
    bin_dir, state_path, root = locations(system)
    selected = set(args.component) if args.component else None
    if selected is not None:
        component_commands(selected)
    with registry_lock(state_path.parent.parent / "registry.json"):
        if args.action == "install":
            install(bin_dir, state_path, root, system, selected)
        elif args.action == "update":
            state = read_state(state_path, system)
            if not state["commands"]:
                fail(f"{NAME} is not installed in this scope")
            if MANIFEST.get("components"):
                owned = installed_components(state)
                if selected is None:
                    selected = owned
                elif not selected <= owned:
                    fail(f"Components are not installed: {', '.join(sorted(selected - owned))}")
            install(bin_dir, state_path, root, system, selected)
        else:
            uninstall(state_path, read_state(state_path, system), system, args.force, args.purge_config, root, selected)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"{NAME} setup: {error}", file=sys.stderr)
        sys.exit(1)
