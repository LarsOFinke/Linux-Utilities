"""Registry paths, locking, migration, and installed inventory."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from catalog import CATALOG, MODULES, REPOSITORY, installed_components
from core.files import sha256


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


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".registry.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def paths(system: bool) -> tuple[Path, Path, Path]:
    if system:
        prefix = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
        if prefix == Path("/") and os.geteuid() != 0:
            raise RuntimeError("Use sudo for --system installation or removal.")
        return (
            prefix / CATALOG["scopes"]["system"]["bin_dir"],
            prefix / CATALOG["scopes"]["system"]["registry"],
            prefix,
        )
    home = Path.home()
    return (
        home / CATALOG["scopes"]["user"]["bin_dir"],
        home / CATALOG["scopes"]["user"]["registry"],
        home,
    )


def read_registry(path: Path, scope: str, bin_dir: Path) -> dict:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symbolic-link registry: {path}")
    if not path.exists():
        return {
            "schema_version": 1,
            "scope": scope,
            "bin_dir": str(bin_dir),
            "modules": {},
            "profile_added": False,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("scope") != scope:
        raise RuntimeError(f"Unsupported or mismatched registry: {path}")
    if data.get("bin_dir") != str(bin_dir):
        raise RuntimeError(f"Registry uses a different command directory: {path}")
    if not isinstance(data.get("modules"), dict):
        raise RuntimeError(f"Registry has no valid module map: {path}")
    migrate_legacy_system_update(data)
    return data


def migrate_legacy_system_update(registry: dict) -> None:
    """Preserve ownership when the old system:update component becomes a module."""
    modules = registry["modules"]
    old = modules.get("system")
    if not old or "update-system" not in old["commands"]:
        return
    if "system-update" in modules:
        raise RuntimeError("Both system:update and system-update claim update-system in the registry")
    update = copy.deepcopy(old)
    update["commands"] = {"update-system": old["commands"].pop("update-system")}
    update["commands"]["update-system"]["source"] = str(
        REPOSITORY / MODULES["system-update"]["commands"]["update-system"])
    update["setup_script"] = str(REPOSITORY / MODULES["system-update"]["setup"])
    update["documentation"] = str(REPOSITORY / MODULES["system-update"]["documentation"])
    update["config_examples"] = []
    update["cron_templates"] = []
    update["managed_cron_files"] = {}
    update["runtime_configs"] = []
    update["schedules"] = []
    update["pre_remove"] = None
    update.pop("components", None)
    modules["system-update"] = update
    if old["commands"]:
        old["components"] = sorted(installed_components("system", {**old, "components": None}))
    else:
        del modules["system"]


def registry_inventory(registry: dict) -> dict[str, dict]:
    """Report registered ownership and check its installed files."""
    inventory = {}
    for module, entry in registry["modules"].items():
        components = ([name for name in MODULES[module]["components"]
                       if name in installed_components(module, entry)]
                      if module in MODULES and MODULES[module]["components"] else None)
        issues = []
        updates = []
        files = [(f"command {name}", Path(record["path"]), record["sha256"])
                 for name, record in entry["commands"].items()]
        files.extend((f"cron {path}", Path(path), record["sha256"])
                     for path, record in entry.get("managed_cron_files", {}).items())
        for label, path, recorded_hash in files:
            if path.is_symlink() or not path.is_file():
                issues.append(f"{label} is missing or not a regular file")
            else:
                try:
                    if sha256(path) != recorded_hash:
                        issues.append(f"{label} was modified")
                except OSError as error:
                    issues.append(f"{label} cannot be read: {error}")
        definition = MODULES.get(module)
        if definition:
            for name, record in entry["commands"].items():
                source_relative = definition["commands"].get(name)
                if not source_relative:
                    continue
                source = REPOSITORY / source_relative
                if source.is_file() and record.get("source_sha256") != sha256(source):
                    updates.append(name)
        inventory[module] = {"components": components, "issues": issues, "updates": updates}
    return inventory
