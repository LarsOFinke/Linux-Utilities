"""Unpack a module received on standard input and run its requested action."""

import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile

options = json.loads(sys.argv[1])
with tempfile.TemporaryDirectory(prefix="linux-utilities-") as temporary:
    root = pathlib.Path(temporary)
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = pathlib.PurePosixPath(member.name).parts
            if not parts or parts[0] != "module" or ".." in parts or not (member.isfile() or member.isdir()):
                raise RuntimeError("Unsafe module archive member")
        archive.extractall(root)
    command = [sys.executable, str(root / "module" / "portable_module.py"), options["action"]]
    if options["system"]:
        command.append("--system")
    if options["force"]:
        command.append("--force")
    for name in options["components"]:
        command.extend(("--component", name))
    if options["system"] and os.geteuid() != 0 and pathlib.Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve() == pathlib.Path("/"):
        command = ["sudo", "-n", "--", *command]
    sys.exit(subprocess.call(command))
