#!/usr/bin/env python3
"""Exercise install rollback and catalog command removal under a temporary home."""

from __future__ import annotations

import copy
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from catalog import CATALOG, MODULES
from core.files import copy_command
from core.registry import paths, read_registry
from setup import install as install_logic


def current_install(*modules: str) -> tuple[Path, Path]:
    bin_dir, registry_path, _ = paths(False)
    registry = read_registry(registry_path, "user", bin_dir)
    install_logic.install(list(modules), registry, bin_dir, registry_path, False)
    return bin_dir, registry_path


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        with patch.dict(os.environ, HOME=str(home)):
            bin_dir, registry_path = current_install("backup")
            original_registry = registry_path.read_bytes()
            original_command = (bin_dir / "backup-home").read_bytes()
            original_profile = (home / ".profile").read_bytes()
            real_copy = copy_command
            copies = 0

            def failing_copy(source: Path, target: Path, executable: bool) -> None:
                nonlocal copies
                copies += 1
                if copies == 2:
                    raise OSError("simulated copy failure")
                real_copy(source, target, executable)

            with patch.object(install_logic, "copy_command", failing_copy):
                try:
                    current_install("backup", "privacy")
                except OSError as error:
                    assert "simulated copy failure" in str(error)
                else:
                    raise AssertionError("Expected the batch install to fail")
            assert registry_path.read_bytes() == original_registry
            assert (bin_dir / "backup-home").read_bytes() == original_command
            assert (home / ".profile").read_bytes() == original_profile
            assert not (bin_dir / "privacy-cleanup").exists()

            with patch.object(install_logic, "atomic_json", side_effect=OSError("registry failure")):
                try:
                    current_install("privacy")
                except OSError as error:
                    assert "registry failure" in str(error)
                else:
                    raise AssertionError("Expected registry write to fail")
            assert registry_path.read_bytes() == original_registry
            assert not (bin_dir / "privacy-cleanup").exists()

            obsolete = bin_dir / "backup-home-cron"
            catalog = copy.deepcopy(MODULES)
            del catalog["backup"]["commands"]["backup-home-cron"]
            with patch.object(install_logic, "MODULES", catalog):
                current_install("backup")
            assert not obsolete.exists()
            registry = read_registry(registry_path, "user", bin_dir)
            assert "backup-home-cron" not in registry["modules"]["backup"]["commands"]

            with patch.object(install_logic, "MODULES", CATALOG["modules"]):
                current_install("backup")
            obsolete.write_text("locally edited\n", encoding="utf-8")
            before = registry_path.read_bytes()
            with patch.object(install_logic, "MODULES", catalog):
                try:
                    current_install("backup")
                except RuntimeError as error:
                    assert "changed locally" in str(error)
                else:
                    raise AssertionError("Expected locally edited obsolete command to be preserved")
            assert obsolete.read_text(encoding="utf-8") == "locally edited\n"
            assert registry_path.read_bytes() == before

        system_root = home / "system-root"
        with patch.dict(os.environ, SHELL_SCRIPTS_INSTALL_ROOT=str(system_root)):
            bin_dir, registry_path, _ = paths(True)
            registry = read_registry(registry_path, "system", bin_dir)
            install_logic.install(["network"], registry, bin_dir, registry_path, True)
            cron = system_root / "etc/cron.d/capture-traffic"
            original_cron = cron.read_bytes()
            original_registry = registry_path.read_bytes()
            with patch.object(install_logic, "atomic_json", side_effect=OSError("registry failure")):
                try:
                    registry = read_registry(registry_path, "system", bin_dir)
                    install_logic.install(["network", "privacy"], registry, bin_dir, registry_path, True)
                except OSError as error:
                    assert "registry failure" in str(error)
                else:
                    raise AssertionError("Expected system registry write to fail")
            assert cron.read_bytes() == original_cron
            assert registry_path.read_bytes() == original_registry
            assert not (bin_dir / "privacy-cleanup").exists()

            catalog = copy.deepcopy(MODULES)
            del catalog["network"]["system_cron"]
            with patch.object(install_logic, "MODULES", catalog):
                registry = read_registry(registry_path, "system", bin_dir)
                install_logic.install(["network"], registry, bin_dir, registry_path, True)
            assert not cron.exists()
            registry = read_registry(registry_path, "system", bin_dir)
            assert not registry["modules"]["network"]["managed_cron_files"]
    print("Installation transaction tests passed")


if __name__ == "__main__":
    main()
