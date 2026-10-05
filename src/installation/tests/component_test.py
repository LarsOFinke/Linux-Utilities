#!/usr/bin/env python3
"""Check independent component lifecycle and migration of the former update component."""

from __future__ import annotations

import json
import os
import pty
import shutil
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
SYSTEM = REPOSITORY / "src/modules/system-utilities/system"


def run(*args: str | Path, environment: dict[str, str]) -> str:
    return subprocess.run([str(arg) for arg in args], env=environment, check=True,
                          capture_output=True, text=True).stdout


def records(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["modules"]


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

        catalog = json.loads((REPOSITORY / "configuration/install.json").read_text(encoding="utf-8"))["modules"]
        system_modules = sorted(
            name for name, manifest in catalog.items()
            if json.loads((REPOSITORY / manifest).read_text(encoding="utf-8"))["category"]
            == "System utilities"
        )
        system_choice = system_modules.index("system") + 1

        output = interactive(REPOSITORY / "setup.sh", f"4\n{system_choice}\n1\n".encode(), environment)
        assert "Categories:" in output and "System utilities modules:" in output
        assert f"{system_choice}. system" in output and "1. amd-gaming" in output
        assert set(records(registry)["system"]["commands"]) == {"install-amd-gaming"}
        output = interactive(REPOSITORY / "setup.sh", f"4\n{system_choice}\n1\n".encode(), environment)
        assert "1. h848-audio" in output and "amd-gaming —" not in output
        assert "install-h848-audio-fix" in records(registry)["system"]["commands"]
        output = interactive(REPOSITORY / "uninstall.sh", b"1\n1\n1\n", environment)
        assert "1. amd-gaming" in output and "2. h848-audio" in output
        assert "install-amd-gaming" not in records(registry)["system"]["commands"]
        run(REPOSITORY / "uninstall.sh", "--module", "system", environment=environment)
        assert "system" not in records(registry)

        run(REPOSITORY / "setup.sh", "--module", "system-update", environment=environment)
        run(REPOSITORY / "setup.sh", "--component", "system:amd-gaming", environment=environment)
        update = binary / "update-system"
        original_update = update.read_bytes()
        update.write_bytes(original_update + b"# local edit\n")
        run(SYSTEM / "setup.sh", "--component", "h848-audio", environment=environment)
        assert update.read_bytes() == original_update + b"# local edit\n"
        update.write_bytes(original_update)

        # Simulate a registry written by the previous three-component system module.
        record = json.loads(registry.read_text(encoding="utf-8"))
        old = record["modules"].pop("system-update")
        system = record["modules"]["system"]
        system["commands"].update(old["commands"])
        system["components"] = ["update", "amd-gaming", "h848-audio"]
        registry.write_text(json.dumps(record), encoding="utf-8")
        listed = run(REPOSITORY / "uninstall.sh", "--list", environment=environment)
        assert "system-update [user]" in listed
        assert "system:amd-gaming" in listed and "system:h848-audio" in listed
        run(REPOSITORY / "uninstall.sh", "--module", "system-update", environment=environment)
        assert not update.exists()
        assert "system-update" not in records(registry)
        assert "install-h848-audio-fix" in records(registry)["system"]["commands"]
        run(SYSTEM / "uninstall.sh", "--component", "h848-audio", environment=environment)
        run(REPOSITORY / "uninstall.sh", "--module", "system", environment=environment)

        copied = root / "copied-system"
        shutil.copytree(SYSTEM, copied, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        run(copied / "setup.sh", "--component", "amd-gaming", environment=environment)
        portable = home / ".local/state/shell-scripts/portable/system.json"
        assert set(json.loads(portable.read_text(encoding="utf-8"))["commands"]) == {"install-amd-gaming"}
        run(copied / "setup.sh", "--component", "h848-audio", environment=environment)
        run(copied / "uninstall.sh", "--component", "amd-gaming", environment=environment)
        assert (binary / "install-h848-audio-fix").exists()
        run(copied / "uninstall.sh", "--component", "h848-audio", environment=environment)
        assert not portable.exists()
    print("Component lifecycle tests passed")


if __name__ == "__main__":
    main()
