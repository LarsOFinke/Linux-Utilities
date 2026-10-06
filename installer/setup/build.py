"""Build generated commands before installation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from catalog import MODULES, REPOSITORY, component_commands

def build_commands(selected: list[str], directory: Path,
                   components: dict[str, set[str] | None] | None = None) -> dict[tuple[str, str], Path]:
    built = {}
    for module in selected:
        requested = (components or {}).get(module)
        allowed = None if requested is None else component_commands(module, requested)
        for name, script in MODULES[module].get("build_commands", {}).items():
            if allowed is not None and name not in allowed:
                continue
            path = REPOSITORY / script
            if not path.is_file():
                raise RuntimeError(f"Missing build script for {module}: {path}")
            output = directory / f"{module}-{name}"
            subprocess.run([str(path), str(output)], check=True)
            if not output.is_file():
                raise RuntimeError(f"Build script did not produce {output}")
            built[module, name] = output
    return built
