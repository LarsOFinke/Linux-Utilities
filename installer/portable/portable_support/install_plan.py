"""Validate standalone install inputs and capture the files needed for rollback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .files import check_target, local_path
from .state import component_commands, fail, installed_components, read_state


@dataclass
class InstallationPlan:
    names: set[str]
    writing: set[str]
    commands: dict[str, str]
    previous: dict
    cron: dict | None
    cron_target: Path | None
    stale: dict[Path, dict]
    snapshots: dict[Path, tuple[bytes, int] | None]


def prepare(module: Path, manifest: dict, bin_dir: Path, state_path: Path,
            root: Path, system: bool, selected: set[str] | None, module_id: str) -> InstallationPlan:
    state = read_state(state_path, system, module_id)
    names = (set(manifest.get("components", {})) if selected is None else
             installed_components(state, manifest) | selected)
    allowed = set(manifest["commands"]) if selected is None else component_commands(names, manifest)
    writing = allowed if selected is None else component_commands(selected, manifest)
    commands = {name: source for name, source in manifest["commands"].items() if name in writing}
    previous = state["commands"]
    cron = manifest.get("system_cron") if system else None
    targets = {bin_dir / name: previous.get(name) for name in commands}
    old_cron = state.get("cron", {})
    cron_target = root / "etc/cron.d" / cron["name"] if cron else None
    if cron_target is not None:
        targets[cron_target] = old_cron.get(str(cron_target))
    stale = ({Path(record["path"]): record for name, record in previous.items() if name not in allowed}
             if selected is None else {})
    stale.update({Path(path): record for path, record in old_cron.items() if path != str(cron_target)})
    for path, record in {**targets, **stale}.items():
        check_target(path, record)
    for source in [*commands.values(), *manifest.get("examples", []), *manifest.get("cron_templates", [])]:
        if not local_path(source, module).is_file():
            fail(f"Missing module file: {source}")
    if cron and not local_path(cron["source"], module).is_file():
        fail(f"Missing cron template: {cron['source']}")
    snapshots = {path: (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
                 for path in [*targets, *stale, state_path]}
    return InstallationPlan(names, writing, commands, previous, cron, cron_target, stale, snapshots)
