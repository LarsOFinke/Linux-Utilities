"""Launch OpenSSH with the saved destination and selected authentication method."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from Connection import Connection
from ConnectVpsError import ConnectVpsError


def connect(item: Connection) -> int:
    ssh = shutil.which("ssh")
    if ssh is None:
        raise ConnectVpsError("OpenSSH client 'ssh' is not installed")
    command = [ssh, "-p", str(item.port), "-l", item.user,
               "-o", "BatchMode=no", "-o", "StrictHostKeyChecking=ask",
               "-o", "UserKnownHostsFile=~/.ssh/known_hosts"]
    if item.auth == "key":
        command.extend(["-o", "PreferredAuthentications=publickey",
                        "-o", "PasswordAuthentication=no",
                        "-o", "KbdInteractiveAuthentication=no"])
        if item.key_path is not None:
            if not Path(item.key_path).is_file():
                raise ConnectVpsError(f"private key not found: {item.key_path}")
            # Configured IdentityFile entries are additive, even with IdentitiesOnly=yes.
            command.extend(["-F", "none", "-i", item.key_path, "-o", "IdentitiesOnly=yes"])
    else:
        command.extend(["-o", "PubkeyAuthentication=no",
                        "-o", "PreferredAuthentications=password,keyboard-interactive"])
    command.extend(["--", item.ip])
    print(f"Connecting to {item.name} ({item.user}@{item.ip}:{item.port})...", flush=True)
    return subprocess.run(command, check=False).returncode
