"""Standalone registry locking, scope paths, and component state."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def registry_lock(path: Path):
    """Serialize the complete read/modify/publish operation; never unlink the lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor = os.open(path.parent / "registry.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RuntimeError("Registry lock must be a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def fail(message: str) -> None:
    raise RuntimeError(message)


def locations(system: bool, name: str) -> tuple[Path, Path, Path]:
    if system:
        root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
        if root == Path("/") and os.geteuid() != 0:
            fail("Use sudo for a system installation.")
        return root / "usr/local/bin", root / "var/lib/shell-scripts/portable" / f"{name}.json", root
    home = Path.home()
    return home / ".local/bin", home / ".local/state/shell-scripts/portable" / f"{name}.json", home


def read_state(path: Path, system: bool, name: str) -> dict:
    if path.is_symlink():
        fail(f"Refusing symbolic-link state: {path}")
    if not path.exists():
        return {"id": name, "system": system, "commands": {}, "cron": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("id") != name or state.get("system") != system:
        fail(f"Invalid standalone installation state: {path}")
    return state


def component_commands(names: set[str], manifest: dict) -> set[str]:
    components = manifest.get("components", {})
    unknown = names - components.keys()
    if unknown:
        fail(f"Unknown component: {', '.join(sorted(unknown))}")
    return {command for name in names for command in components[name]["commands"]}


def installed_components(state: dict, manifest: dict) -> set[str]:
    components = manifest.get("components", {})
    recorded = state.get("components")
    if recorded is not None:
        names = set(recorded)
    else:
        owned = set(state["commands"])
        names = {name for name, item in components.items() if owned.intersection(item["commands"])}
    owned = set(state["commands"])
    expected = component_commands(names, manifest)
    legacy_h848 = {"h848_wireplumber_05.conf", "h848_wireplumber_04.lua", "h848_audio_guard.service"}
    compatible = (manifest["id"] == "system" and owned <= expected
                  and expected - owned <= legacy_h848)
    if owned != expected and not compatible:
        fail("Cannot infer components from standalone installation state")
    return names
