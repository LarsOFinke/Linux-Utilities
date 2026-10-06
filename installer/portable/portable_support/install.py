"""Plan and apply standalone installations with rollback."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .files import atomic_copy, atomic_json, digest, local_path, restore_snapshot
from .install_plan import prepare
from .state import fail


def install(bin_dir: Path, state_path: Path, root: Path, system: bool,
            selected: set[str] | None = None, *, module: Path, manifest: dict, module_id: str) -> None:
    plan = prepare(module, manifest, bin_dir, state_path, root, system, selected, module_id)
    with tempfile.TemporaryDirectory(prefix=f"{module_id}-build-") as directory:
        built = {}
        for name, script in manifest.get("build_commands", {}).items():
            if name not in plan.writing:
                continue
            output = Path(directory) / name
            subprocess.run([str(local_path(script, module)), str(output)], check=True)
            if not output.is_file():
                fail(f"Build script produced no output: {script}")
            built[name] = output
        try:
            installed = {} if selected is None else dict(plan.previous)
            for name, source in plan.commands.items():
                target = bin_dir / name
                atomic_copy(built.get(name, local_path(source, module)), target, name not in manifest.get("non_executable_commands", []))
                installed[name] = {"path": str(target), "sha256": digest(target)}
            installed_cron = {}
            if plan.cron and plan.cron_target is not None:
                atomic_copy(local_path(plan.cron["source"], module), plan.cron_target, False)
                installed_cron[str(plan.cron_target)] = {"path": str(plan.cron_target), "sha256": digest(plan.cron_target)}
            for path in plan.stale:
                path.unlink(missing_ok=True)
            atomic_json(state_path, {"id": module_id, "system": system, "commands": installed,
                                     "cron": installed_cron, "pre_remove": manifest.get("pre_remove"),
                                     **({"components": sorted(plan.names)} if manifest.get("components") else {})})
        except BaseException:
            for path, original in reversed(list(plan.snapshots.items())):
                restore_snapshot(path, original)
            raise
    print(f"Installed {manifest['display_name']} to {bin_dir}")
