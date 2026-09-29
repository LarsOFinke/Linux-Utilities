#!/usr/bin/env python3
"""Check independent system utility ownership in shared and copied installs."""

from __future__ import annotations

import json
import os
import pty
import shutil
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
SYSTEM = REPOSITORY / "src/system"


def run(*args: str | Path, environment: dict[str, str]) -> None:
    subprocess.run([str(arg) for arg in args], env=environment, check=True,
                   stdout=subprocess.DEVNULL)


def commands(path: Path) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8"))["modules"]["system"]["commands"])


def interactive(command: Path, answers: bytes, environment: dict[str, str]) -> str:
    master, slave = pty.openpty()
    try:
        process = subprocess.Popen([str(command)], cwd=REPOSITORY, env=environment,
                                   stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        slave = -1
        os.write(master, answers)
        assert process.wait(timeout=15) == 0
        output = bytearray()
        while True:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            output.extend(chunk)
        return output.decode("utf-8", errors="replace")
    finally:
        if slave >= 0:
            os.close(slave)
        os.close(master)


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        home = root / "home"
        home.mkdir()
        environment = dict(os.environ, HOME=str(home),
                           SHELL_SCRIPTS_INSTALL_ROOT=str(root / "system-root"),
                           PYTHONDONTWRITEBYTECODE="1")
        binary = home / ".local/bin"
        registry = home / ".local/state/shell-scripts/registry.json"

        output = interactive(REPOSITORY / "setup.sh", b"5\n1\n", environment)
        assert "5. system" in output and "1. update" in output
        assert commands(registry) == {"update-system"}
        output = interactive(REPOSITORY / "setup.sh", b"5\n1\n", environment)
        assert "1. amd-gaming" in output and "update —" not in output
        assert commands(registry) == {"update-system", "install-amd-gaming"}
        output = interactive(REPOSITORY / "uninstall.sh", b"1\n2\n", environment)
        assert "1. update" in output and "2. amd-gaming" in output
        assert commands(registry) == {"update-system"}
        listed = subprocess.run([str(REPOSITORY / "uninstall.sh"), "--list"], env=environment,
                                text=True, capture_output=True, check=True).stdout
        assert "system:amd-gaming" not in listed
        run(REPOSITORY / "uninstall.sh", "--module", "system", environment=environment)

        run(REPOSITORY / "setup.sh", "--component", "system:update", environment=environment)
        assert commands(registry) == {"update-system"}
        assert not (binary / "install-amd-gaming").exists()
        update = binary / "update-system"
        original_update = update.read_bytes()
        update.write_bytes(original_update + b"# local edit\n")
        run(SYSTEM / "setup.sh", "--component", "h848-audio", environment=environment)
        assert update.read_bytes() == original_update + b"# local edit\n"
        assert commands(registry) == {"update-system", "install-h848-audio-fix",
                                      "uninstall-h848-audio-fix", "h848_audio_lifecycle.sh",
                                      "h848_audio_guard.sh"}
        update.write_bytes(original_update)
        run(REPOSITORY / "uninstall.sh", "--component", "system:update", environment=environment)
        assert not (binary / "update-system").exists()
        assert (binary / "install-h848-audio-fix").exists()
        run(SYSTEM / "uninstall.sh", "--component", "h848-audio", environment=environment)
        assert "system" not in json.loads(registry.read_text(encoding="utf-8"))["modules"]

        run(REPOSITORY / "setup.sh", "--module", "system", environment=environment)
        record = json.loads(registry.read_text(encoding="utf-8"))
        del record["modules"]["system"]["components"]  # registry written by an older version
        registry.write_text(json.dumps(record), encoding="utf-8")
        run(REPOSITORY / "uninstall.sh", "--component", "system:amd-gaming", environment=environment)
        assert not (binary / "install-amd-gaming").exists()
        assert (binary / "update-system").exists()
        assert (binary / "install-h848-audio-fix").exists()
        run(REPOSITORY / "uninstall.sh", "--module", "system", environment=environment)

        copied = root / "copied-system"
        shutil.copytree(SYSTEM, copied, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        run(copied / "setup.sh", "--component", "update", environment=environment)
        portable = home / ".local/state/shell-scripts/portable/system.json"
        assert set(json.loads(portable.read_text(encoding="utf-8"))["commands"]) == {"update-system"}
        original_update = update.read_bytes()
        update.write_bytes(original_update + b"# local edit\n")
        run(copied / "setup.sh", "--component", "amd-gaming", environment=environment)
        assert update.read_bytes() == original_update + b"# local edit\n"
        update.write_bytes(original_update)
        run(copied / "uninstall.sh", "--component", "update", environment=environment)
        assert not (binary / "update-system").exists()
        assert (binary / "install-amd-gaming").exists()
        run(copied / "uninstall.sh", "--component", "amd-gaming", environment=environment)
        assert not portable.exists()
    print("Component lifecycle tests passed")


if __name__ == "__main__":
    main()
