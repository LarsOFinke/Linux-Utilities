"""Small SSH transport for independent portable modules and local deployment records."""

from __future__ import annotations

import io
import json
import os
import re
import shlex
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from catalog import MODULES, REPOSITORY
from manage import atomic_json, paths, read_registry, registry_lock

BOOTSTRAP = r'''
import json, os, pathlib, subprocess, sys, tarfile, tempfile
options = json.loads(sys.argv[1])
with tempfile.TemporaryDirectory(prefix="linux-utilities-") as temporary:
    root = pathlib.Path(temporary)
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = pathlib.PurePosixPath(member.name).parts
            if not parts or parts[0] != "module" or ".." in parts or not (member.isfile() or member.isdir()):
                raise RuntimeError("Unsafe module archive member")
        archive.extractall(root)
    command = [str(root / "module" / ("setup.sh" if options["action"] == "install" else "uninstall.sh"))]
    if options["system"]:
        command.append("--system")
    if options["force"]:
        command.append("--force")
    for name in options["components"]:
        command.extend(("--component", name))
    if options["system"] and os.geteuid() != 0 and pathlib.Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve() == pathlib.Path("/"):
        command = ["sudo", "-n", "--", *command]
    sys.exit(subprocess.call(command))
'''

SCAN = r'''
import hashlib, json, os, pathlib, sys
system = sys.argv[1] == "system"
base = pathlib.Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve() if system else pathlib.Path.home()
directory = base / ("var/lib/shell-scripts/portable" if system else ".local/state/shell-scripts/portable")
result = {}
for path in directory.glob("*.json"):
    if path.is_symlink():
        continue
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("id") != path.stem or state.get("system") != system:
            continue
        issues = []
        for name, record in state.get("commands", {}).items():
            command = pathlib.Path(record["path"])
            if command.is_symlink() or not command.is_file():
                issues.append("missing command " + name)
            elif hashlib.sha256(command.read_bytes()).hexdigest() != record["sha256"]:
                issues.append("modified command " + name)
        result[path.stem] = {"components": state.get("components"), "issues": issues}
    except (OSError, ValueError, KeyError, TypeError):
        result[path.stem] = {"components": None, "issues": ["invalid remote portable state"]}
print(json.dumps(result))
'''


def valid_target(target: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", target) or target.count("@") > 1:
        raise RuntimeError(f"Invalid SSH target: {target!r}")
    return target


def local_registry() -> tuple[dict, Path]:
    bin_dir, path, _ = paths(False)
    return read_registry(path, "user", bin_dir), path


def cached(target: str, scope: str) -> dict:
    registry, _ = local_registry()
    return registry.get("remote_deployments", {}).get(valid_target(target), {}).get(scope, {})


def scan_remote(target: str, scope: str) -> dict:
    valid_target(target)
    command = "python3 -c " + shlex.quote(SCAN) + " " + shlex.quote(scope)
    if scope == "system":
        command = "sudo -n -- " + command
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", target, command],
                            capture_output=True, text=True, check=True)
    return {module: entry for module, entry in json.loads(result.stdout).items() if module in MODULES}


def record(target: str, scope: str, module: str, components: set[str] | None, action: str) -> None:
    with registry_lock(paths(False)[1]):
        registry, path = local_registry()
        deployments = registry.setdefault("remote_deployments", {})
        scopes = deployments.setdefault(target, {})
        entries = scopes.setdefault(scope, {})
        if action == "install":
            names = set(MODULES[module]["components"]) if components is None else components
            previous = entries.get(module, {}).get("components", [])
            entries[module] = {"components": sorted(set(previous) | names) if MODULES[module]["components"] else None,
                               "updated_at": datetime.now(timezone.utc).isoformat()}
        elif module in entries:
            if components is None or not MODULES[module]["components"]:
                del entries[module]
            else:
                remaining = set(entries[module]["components"] or []) - components
                if remaining:
                    entries[module]["components"] = sorted(remaining)
                else:
                    del entries[module]
        if not entries:
            del scopes[scope]
        if not scopes:
            del deployments[target]
        registry["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(path, registry)


def archive_module(module: str) -> bytes:
    definition = MODULES[module]
    directory = (REPOSITORY / definition["manifest"]).parent
    tracked = subprocess.run(["git", "-C", str(REPOSITORY), "ls-files", "-z", "--",
                              str(directory.relative_to(REPOSITORY))],
                             capture_output=True, check=True).stdout.split(b"\0")
    files = {REPOSITORY / os.fsdecode(name) for name in tracked if name}
    required = [definition["manifest"], definition["setup"], definition["documentation"],
                *definition["commands"].values(), *definition["examples"],
                *definition["cron_templates"], *definition["build_commands"].values()]
    files.update(REPOSITORY / name for name in required)
    files.update((directory / "uninstall.sh", directory / "portable_module.py"))
    for path in (REPOSITORY / name for name in required):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Missing module source for SSH deployment: {path}")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for path in sorted(files):
            if not path.is_relative_to(directory) or not path.is_file() or path.is_symlink():
                continue
            archive.add(path, arcname=str(Path("module") / path.relative_to(directory)), recursive=False)
    return stream.getvalue()


def deploy(target: str, selection: dict[str, set[str] | None], system: bool,
           action: str = "install", force: bool = False) -> None:
    valid_target(target)
    scope = "system" if system else "user"
    # Check the local registry before changing the remote host.
    local_registry()
    for module, components in selection.items():
        if scope not in MODULES[module]["scopes"]:
            raise RuntimeError(f"{module} does not support {scope} installation")
        options = {"action": action, "system": system, "force": force,
                   "components": sorted(components or [])}
        remote_command = "python3 -c " + shlex.quote(BOOTSTRAP) + " " + shlex.quote(json.dumps(options))
        subprocess.run(["ssh", "-o", "BatchMode=yes", target, remote_command],
                       input=archive_module(module), check=True)
        try:
            record(target, scope, module, components, action)
        except (OSError, RuntimeError) as error:
            raise RuntimeError(f"Remote {action} of {module} succeeded on {target}, but local registry update failed: {error}") from error
        print(f"{action.title()}ed {module} on {target} [{scope}]")
