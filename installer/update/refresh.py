"""Refresh only commands and components already installed."""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from catalog import MODULES, installed_components
from core.registry import read_registry, registry_lock
from setup.build import build_commands
from setup.install import apply_installation

def update(selected: list[str], bin_dir: Path, registry_path: Path, system: bool,
           components: dict[str, set[str] | None] | None = None) -> None:
    """Refresh installed commands from this checkout without adding modules/components."""
    with registry_lock(registry_path):
        current = read_registry(registry_path, "system" if system else "user", bin_dir)
        missing = set(selected) - current["modules"].keys()
        if missing:
            raise RuntimeError(f"Modules are not installed in this scope: {', '.join(sorted(missing))}")
        requested = copy.deepcopy(components or {})
        for module in selected:
            if module not in MODULES:
                raise RuntimeError(f"Module is no longer available in this checkout: {module}")
            definition = MODULES[module]
            entry = current["modules"][module]
            if definition["components"]:
                installed = installed_components(module, entry)
                selected_components = requested.get(module)
                if selected_components is None:
                    requested[module] = installed
                elif not selected_components <= installed:
                    raise RuntimeError(
                        f"Components are not installed for {module}: "
                        f"{', '.join(sorted(selected_components - installed))}"
                    )
                if not requested[module]:
                    raise RuntimeError(f"No installed components selected for update: {module}")
        with tempfile.TemporaryDirectory(prefix="linux-utilities-update-") as directory:
            built = build_commands(selected, Path(directory), requested)
            apply_installation(selected, current, bin_dir, registry_path, system, built, requested, updating=True)
