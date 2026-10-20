"""Build generated commands before installation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from catalog import MODULES, REPOSITORY, component_commands
from portable.portable_support.bundle import build as build_bundle
from portable.portable_support.dependencies import ensure_build_dependencies

def build_commands(selected: list[str], directory: Path,
                   components: dict[str, set[str] | None] | None = None) -> dict[tuple[str, str], Path]:
    ensure_build_dependencies()
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
        definition = MODULES[module]
        files = {name: REPOSITORY / source for name, source in definition["commands"].items()}
        files.update({name: REPOSITORY / source for name, source in definition["bundle_files"].items()})
        for name, script in definition["build_files"].items():
            path = REPOSITORY / script
            output = directory / f"{module}-file-{name}"
            subprocess.run([str(path), str(output)], check=True)
            if not output.is_file():
                raise RuntimeError(f"Build script did not produce {output}")
            files[name] = output
        executable = set(definition["commands"]) - set(definition.get("non_executable_commands", []))
        prebuilt = dict(built)
        for name in definition["bundle_commands"]:
            if allowed is not None and name not in allowed:
                continue
            sources = {key: prebuilt.get((module, key), path) for key, path in files.items()}
            output = directory / f"{module}-{name}"
            build_bundle(name, sources, executable, output)
            built[module, name] = output
    return built
