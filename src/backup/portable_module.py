#!/usr/bin/env python3
"""Standalone installer copied with each module; keep copies byte-for-byte in sync."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MODULE = Path(__file__).resolve().parent
MANIFEST = json.loads((MODULE / "module.json").read_text(encoding="utf-8"))
NAME = MANIFEST["id"]


def fail(message: str) -> None:
    raise RuntimeError(message)


def local_path(value: str) -> Path:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", value):
        fail(f"Invalid module path: {value!r}")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        fail(f"Unsafe module path: {value!r}")
    return MODULE / path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_copy(source: Path, target: Path, executable: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".module-install-", dir=target.parent)
    os.close(descriptor)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o755 if executable else 0o644)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".module-state-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def restore_snapshot(path: Path, original: tuple[bytes, int] | None) -> None:
    if original is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".module-restore-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(original[0])
        os.chmod(temporary, original[1])
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def locations(system: bool) -> tuple[Path, Path, Path]:
    if system:
        root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
        if root == Path("/") and os.geteuid() != 0:
            fail("Use sudo for a system installation.")
        return root / "usr/local/bin", root / "var/lib/shell-scripts/portable" / f"{NAME}.json", root
    home = Path.home()
    return home / ".local/bin", home / ".local/state/shell-scripts/portable" / f"{NAME}.json", home


def read_state(path: Path, system: bool) -> dict:
    if path.is_symlink():
        fail(f"Refusing symbolic-link state: {path}")
    if not path.exists():
        return {"id": NAME, "system": system, "commands": {}, "cron": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("id") != NAME or state.get("system") != system:
        fail(f"Invalid standalone installation state: {path}")
    return state


def check_target(path: Path, record: dict | None, force: bool = False) -> None:
    if path.is_symlink():
        fail(f"Refusing symbolic-link file: {path}")
    if path.exists() and record is None:
        fail(f"Refusing unmanaged file: {path}")
    if path.exists() and record and not force and digest(path) != record["sha256"]:
        fail(f"Installed file changed locally: {path}")


def hook_command(state: dict, system: bool, purge_config: bool, root: Path) -> tuple[list[str], dict[str, str]] | None:
    hook = state.get("pre_remove") or MANIFEST.get("pre_remove")
    if not hook:
        return None
    record = state["commands"][hook["command"]]
    executable = Path(record["path"])
    if not executable.is_file() or executable.is_symlink() or digest(executable) != record["sha256"]:
        fail(f"Cannot safely run module removal hook: {executable}")
    command = [str(executable)]
    if system and hook.get("system_arg"):
        command.append(hook["system_arg"])
    command.extend(hook["args"])
    if purge_config and hook.get("purge_arg"):
        command.append(hook["purge_arg"])
    environment = dict(os.environ)
    if hook.get("root_env"):
        environment[hook["root_env"]] = str(root)
    return command, environment


def install(bin_dir: Path, state_path: Path, root: Path, system: bool) -> None:
    state = read_state(state_path, system)
    commands = MANIFEST["commands"]
    previous = state["commands"]
    cron = MANIFEST.get("system_cron") if system else None
    targets = {bin_dir / name: previous.get(name) for name in commands}
    old_cron = state.get("cron", {})
    if cron:
        cron_target = root / "etc/cron.d" / cron["name"]
        targets[cron_target] = old_cron.get(str(cron_target))
    stale = {Path(record["path"]): record for name, record in previous.items() if name not in commands}
    stale.update({Path(path): record for path, record in old_cron.items() if not cron or path != str(cron_target)})
    for path, record in targets.items():
        check_target(path, record)
    for path, record in stale.items():
        check_target(path, record)
    for source in [*commands.values(), *MANIFEST.get("examples", []), *MANIFEST.get("cron_templates", [])]:
        if not local_path(source).is_file():
            fail(f"Missing module file: {source}")
    if cron and not local_path(cron["source"]).is_file():
        fail(f"Missing cron template: {cron['source']}")
    snapshots = {}
    for path in [*targets, *stale, state_path]:
        snapshots[path] = (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
    with tempfile.TemporaryDirectory(prefix=f"{NAME}-build-") as directory:
        built = {}
        for name, script in MANIFEST.get("build_commands", {}).items():
            output = Path(directory) / name
            subprocess.run([str(local_path(script)), str(output)], check=True)
            if not output.is_file():
                fail(f"Build script produced no output: {script}")
            built[name] = output
        try:
            installed = {}
            for name, source in commands.items():
                target = bin_dir / name
                atomic_copy(built.get(name, local_path(source)), target, name not in MANIFEST.get("non_executable_commands", []))
                installed[name] = {"path": str(target), "sha256": digest(target)}
            installed_cron = {}
            if cron:
                atomic_copy(local_path(cron["source"]), cron_target, False)
                installed_cron[str(cron_target)] = {"path": str(cron_target), "sha256": digest(cron_target)}
            for path in stale:
                path.unlink(missing_ok=True)
            atomic_json(state_path, {"id": NAME, "system": system, "commands": installed,
                                     "cron": installed_cron, "pre_remove": MANIFEST.get("pre_remove")})
        except Exception:
            for path, original in reversed(list(snapshots.items())):
                restore_snapshot(path, original)
            raise
    print(f"Installed {MANIFEST['display_name']} to {bin_dir}")


def uninstall(state_path: Path, state: dict, system: bool, force: bool, purge_config: bool, root: Path) -> None:
    if not state_path.exists():
        fail(f"No standalone installation recorded: {NAME}")
    for record in [*state["commands"].values(), *state.get("cron", {}).values()]:
        check_target(Path(record["path"]), record, force)
    hook = hook_command(state, system, purge_config, root)
    if hook:
        subprocess.run(hook[0], env=hook[1], check=True)
    for record in [*state["commands"].values(), *state.get("cron", {}).values()]:
        Path(record["path"]).unlink(missing_ok=True)
    state_path.unlink()
    print(f"Removed {MANIFEST['display_name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--system", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--purge-config", action="store_true")
    parser.add_argument("--no-configure", action="store_true")
    args = parser.parse_args()
    system = args.system or "user" not in MANIFEST["scopes"]
    scope = "system" if system else "user"
    if scope not in MANIFEST["scopes"]:
        fail(f"{NAME} does not support {scope} installation")
    bin_dir, state_path, root = locations(system)
    if args.action == "install":
        install(bin_dir, state_path, root, system)
    else:
        uninstall(state_path, read_state(state_path, system), system, args.force, args.purge_config, root)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"{NAME} setup: {error}", file=sys.stderr)
        sys.exit(1)
