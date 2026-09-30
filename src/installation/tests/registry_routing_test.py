#!/usr/bin/env python3
"""Verify every module connects to its direct and root registry lifecycle."""

from __future__ import annotations

import json
import os
import pty
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
CATALOG = json.loads((REPOSITORY / "configuration/install.json").read_text(encoding="utf-8"))["modules"]
MODULES = tuple(CATALOG)
SYSTEM_ONLY = ("ubuntu-updates", "canary", "vps-gateway")


def run(*args: str | Path, environment: dict[str, str]) -> str:
    result = subprocess.run([str(arg) for arg in args], cwd=REPOSITORY, env=environment,
                            capture_output=True, text=True, check=True)
    return result.stdout


def registered(path: Path) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8"))["modules"])


def module_entry(module: str, entry: str) -> Path:
    return (REPOSITORY / CATALOG[module]).parent / entry


def interactive_uninstall(environment: dict[str, str]) -> None:
    master, slave = pty.openpty()
    try:
        process = subprocess.Popen([str(REPOSITORY / "uninstall.sh")], cwd=REPOSITORY,
                                   env=environment, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        slave = -1
        os.write(master, b"1\n1\n")
        assert process.wait(timeout=20) == 0
    finally:
        if slave >= 0:
            os.close(slave)
        os.close(master)


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        home = base / "home"
        system_root = base / "system"
        home.mkdir()
        environment = dict(os.environ, HOME=str(home), SHELL_SCRIPTS_INSTALL_ROOT=str(system_root),
                           PYTHONDONTWRITEBYTECODE="1")
        user_registry = home / ".local/state/shell-scripts/registry.json"
        system_registry = system_root / "var/lib/shell-scripts/registry.json"

        for module in MODULES:
            run(module_entry(module, "setup.sh"), "--no-configure", environment=environment)
        assert registered(user_registry) == set(MODULES) - set(SYSTEM_ONLY)
        assert registered(system_registry) == set(SYSTEM_ONLY)
        catalog = json.loads((REPOSITORY / "configuration/install.json").read_text(encoding="utf-8"))
        assert set(catalog["modules"]) == set(MODULES)
        for module in MODULES:
            manifest = json.loads((REPOSITORY / catalog["modules"][module]).read_text(encoding="utf-8"))
            registry_path = system_registry if module in SYSTEM_ONLY else user_registry
            entry = json.loads(registry_path.read_text(encoding="utf-8"))["modules"][module]
            assert set(entry["commands"]) == set(manifest["commands"])
            assert all(Path(record["path"]).is_file() for record in entry["commands"].values())
        listing = run(REPOSITORY / "uninstall.sh", "--list", environment=environment)
        assert "warning:" not in listing
        for module in MODULES:
            scope = "system" if module in SYSTEM_ONLY else "user"
            assert f"{module} [{scope}]" in listing

        update = home / ".local/bin/update-system"
        original = update.read_bytes()
        update.write_bytes(original + b"# local edit\n")
        listing = run(REPOSITORY / "uninstall.sh", "--list", environment=environment)
        assert "warning: command update-system was modified" in listing
        update.write_bytes(original)

        for module in SYSTEM_ONLY:
            run(module_entry(module, "uninstall.sh"), environment=environment)
        assert not registered(system_registry)
        for module in ("backup", "privacy", "system", "system-update", "termlay"):
            run(module_entry(module, "uninstall.sh"), environment=environment)
        assert registered(user_registry) == {"network"}

        run(REPOSITORY / "setup.sh", "--system", "--module", "network", environment=environment)
        assert registered(system_registry) == {"network"}
        run(REPOSITORY / "uninstall.sh", "--module", "network", environment=environment)
        assert not registered(user_registry)
        assert registered(system_registry) == {"network"}
        run(REPOSITORY / "src/modules/monitoring/network/uninstall.sh", environment=environment)
        assert not registered(system_registry)
        run(REPOSITORY / "setup.sh", "--system", "--module", "network", environment=environment)
        run(REPOSITORY / "uninstall.sh", "--system", "--module", "network", environment=environment)
        assert not registered(system_registry)

        run(REPOSITORY / "setup.sh", "--system", "--module", "system-update", environment=environment)
        assert registered(system_registry) == {"system-update"}
        run(module_entry("system-update", "uninstall.sh"), environment=environment)
        assert not registered(system_registry)

        run(REPOSITORY / "setup.sh", "--module", "system-update", environment=environment)
        run(REPOSITORY / "setup.sh", "--system", "--component", "system:amd-gaming", environment=environment)
        run(module_entry("system", "uninstall.sh"), "--component", "amd-gaming", environment=environment)
        assert registered(user_registry) == {"system-update"}
        assert not registered(system_registry)
        run(REPOSITORY / "uninstall.sh", "--module", "system-update", environment=environment)
        assert not registered(user_registry)

        run(REPOSITORY / "setup.sh", "--module", "ubuntu-updates", environment=environment)
        assert registered(system_registry) == {"ubuntu-updates"}
        interactive_uninstall(environment)
        assert not registered(system_registry)

        run(REPOSITORY / "setup.sh", "--module", "ubuntu-updates", environment=environment)
        run(REPOSITORY / "uninstall.sh", "--module", "ubuntu-updates", environment=environment)
        assert not registered(system_registry)
    print("Registry routing tests passed")


if __name__ == "__main__":
    main()
