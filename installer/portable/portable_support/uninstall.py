"""Validate and remove standalone installations with rollback."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .files import atomic_json, check_target, restore_snapshot
from .hooks import hook_command
from .state import component_commands, fail, installed_components


def uninstall(state_path: Path, state: dict, system: bool, force: bool, purge_config: bool, root: Path,
              selected: set[str] | None = None, *, manifest: dict, module_id: str) -> None:
    if not state_path.exists():
        fail(f"No standalone installation recorded: {module_id}")
    owned = installed_components(state, manifest) if selected is not None else set()
    if selected is not None and not selected <= owned:
        fail(f"Component is not installed: {', '.join(sorted(selected - owned))}")
    removing = set(state["commands"]) if selected is None else component_commands(selected, manifest)
    records = [state["commands"][name] for name in removing]
    if selected is None:
        records.extend(state.get("cron", {}).values())
    for record in records:
        check_target(Path(record["path"]), record, force)
    hook = hook_command(state, system, purge_config, root, manifest) if selected is None else None
    if hook:
        subprocess.run(hook[0], env=hook[1], check=True)
    files = [Path(record["path"]) for record in records] + [state_path]
    snapshots = {path: (path.read_bytes(), path.stat().st_mode & 0o777)
                 if path.exists() else None for path in files}
    try:
        for record in records:
            Path(record["path"]).unlink(missing_ok=True)
        if selected is None or selected == owned:
            state_path.unlink()
        else:
            for name in removing:
                del state["commands"][name]
            state["components"] = sorted(owned - selected)
            atomic_json(state_path, state)
    except BaseException:
        for path, original in reversed(list(snapshots.items())):
            restore_snapshot(path, original)
        raise
    label = manifest["display_name"] if selected is None else ", ".join(sorted(selected))
    print(f"Removed {label}")
