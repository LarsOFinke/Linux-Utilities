"""Check build prerequisites before touching installation state."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys


def ensure_build_dependencies() -> None:
    if sys.version_info < (3, 9):
        raise RuntimeError("Python 3.9 or newer is required; install your distribution's Python 3.")
    if shutil.which("cc") is not None:
        return
    guidance = "Missing build dependency: cc (C compiler)."
    if shutil.which("apt-get") is None:
        raise RuntimeError(f"{guidance} Install a C toolchain with your distribution's package manager, then retry.")
    prefix = [] if os.geteuid() == 0 else ["sudo", "--"]
    command = [*prefix, "apt-get", "install", "-y", "build-essential"]
    hint = shlex.join(command)
    print(f"{guidance}\nRequired package: build-essential\nInstall command: {hint}", file=sys.stderr)
    if not sys.stdin.isatty():
        raise RuntimeError(f"Noninteractive run: install prerequisites with `{hint}`, then retry. For SSH installs, run this on the target.")
    if prefix and shutil.which("sudo") is None:
        raise RuntimeError("sudo is unavailable. Ask an administrator to install build-essential, then retry.")
    try:
        answer = input("Install the missing build tools now? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in {"y", "yes"}:
        raise RuntimeError("Build prerequisites were not installed; no module files were changed.")
    subprocess.run(command, check=True)
    if shutil.which("cc") is None:
        raise RuntimeError("Package installation finished but cc is still missing from PATH; check the toolchain before retrying.")


def ensure_remote_build_dependencies(target: str) -> None:
    """Ask on the local terminal; SSH's standard input carries the archive later."""
    probe = "import json,os,shutil; print(json.dumps([bool(shutil.which('cc')), bool(shutil.which('apt-get')), os.geteuid() == 0, bool(shutil.which('sudo'))]))"
    ssh = ["ssh", "-o", "BatchMode=yes", target]

    def inspect():
        result = subprocess.run([*ssh, "python3 -c " + shlex.quote(probe)],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    compiler, apt, root, sudo = inspect()
    if compiler:
        return
    if not apt:
        raise RuntimeError(f"Missing cc on {target}; install a C toolchain on the target, then retry.")
    command = ([] if root else ["sudo", "-n", "--"]) + ["apt-get", "install", "-y", "build-essential"]
    hint = shlex.join(command)
    print(f"Missing cc on {target}. Required package: build-essential. Remote command: {hint}", file=sys.stderr)
    if not sys.stdin.isatty():
        raise RuntimeError(f"Install build-essential on {target}, then retry (noninteractive run).")
    if not root and not sudo:
        raise RuntimeError(f"sudo is unavailable on {target}; ask its administrator to install build-essential.")
    try:
        answer = input(f"Install the missing build tools on {target} now? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in {"y", "yes"}:
        raise RuntimeError("Remote build prerequisites were not installed; no modules were deployed.")
    subprocess.run([*ssh, hint], check=True)
    if not inspect()[0]:
        raise RuntimeError(f"cc is still unavailable on {target} after installing build-essential.")
