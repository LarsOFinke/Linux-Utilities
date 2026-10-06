"""Archive, inspect, and deploy standalone modules over SSH."""

from __future__ import annotations

import io
import json
import os
import shlex
import subprocess
import tarfile
from pathlib import Path

from catalog import MODULES, REPOSITORY
from remote.scripts import source
from remote.state import local_registry, record, valid_target


def scan_remote(target: str, scope: str) -> dict:
    valid_target(target)
    command = "python3 -c " + shlex.quote(source("scan")) + " " + shlex.quote(scope)
    if scope == "system":
        command = "sudo -n -- " + command
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", target, command],
                            capture_output=True, text=True, check=True)
    scanned = {module: entry for module, entry in json.loads(result.stdout).items() if module in MODULES}
    for module, entry in scanned.items():
        if not MODULES[module]["components"]:
            entry["components"] = None
    return scanned


def archive_module(module: str) -> bytes:
    definition = MODULES[module]
    directory = (REPOSITORY / definition["manifest"]).parent
    relative = directory.relative_to(REPOSITORY)
    # Include tracked files before and after the src/modules -> src move is staged.
    former = Path("src/modules") / relative.relative_to("src")
    tracked = subprocess.run(["git", "-C", str(REPOSITORY), "ls-files", "-z", "--",
                              str(relative), str(former)],
                             capture_output=True, check=True).stdout.split(b"\0")
    files = set()
    for name in tracked:
        if not name:
            continue
        path = Path(os.fsdecode(name))
        if path.is_relative_to(former):
            path = relative / path.relative_to(former)
        files.add(REPOSITORY / path)
    required = [definition["manifest"], definition["documentation"],
                *definition["commands"].values(), *definition["examples"],
                *definition["cron_templates"], *definition["build_commands"].values()]
    files.update(REPOSITORY / name for name in required)
    for path in (REPOSITORY / name for name in required):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Missing module source for SSH deployment: {path}")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for path in sorted(files):
            if not path.is_relative_to(directory) or not path.is_file() or path.is_symlink():
                continue
            archive.add(path, arcname=str(Path("module") / path.relative_to(directory)), recursive=False)
        portable = REPOSITORY / "installer/portable"
        bundle = [portable / "portable_module.py", *sorted((portable / "portable_support").glob("*.py"))]
        for path in bundle:
            if not path.is_file() or path.is_symlink():
                raise RuntimeError(f"Missing portable SSH helper: {path}")
            archive.add(path, arcname=str(Path("module") / path.relative_to(portable)), recursive=False)
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
        remote_command = "python3 -c " + shlex.quote(source("bootstrap")) + " " + shlex.quote(json.dumps(options))
        subprocess.run(["ssh", "-o", "BatchMode=yes", target, remote_command],
                       input=archive_module(module), check=True)
        try:
            record(target, scope, module, components, action)
        except (OSError, RuntimeError) as error:
            raise RuntimeError(
                f"Remote {action} of {module} succeeded on {target}, "
                f"but local registry update failed: {error}"
            ) from error
        verb = {"install": "Installed", "update": "Updated", "uninstall": "Removed"}[action]
        print(f"{verb} {module} on {target} [{scope}]")
