#!/usr/bin/env python3
"""Check stale selections, cross-process locking, and safe profile cleanup."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from catalog import REPOSITORY
from core.profile import DEFAULT_PROFILE_LINE
from core.registry import paths, read_registry, registry_lock
from setup.install import install
from uninstall.remove import uninstall
from remote.state import record


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        environment = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
        with patch.object(Path, "home", return_value=home):
            bin_dir, registry_path, _ = paths(False)
            first = read_registry(registry_path, "user", bin_dir)
            stale = read_registry(registry_path, "user", bin_dir)
            install(["backup"], first, bin_dir, registry_path, False)
            record("demo", "user", "network", None, "install")
            install(["system-update"], stale, bin_dir, registry_path, False)
            state = read_registry(registry_path, "user", bin_dir)
            assert set(state["modules"]) == {"backup", "system-update"}
            assert "network" in state["remote_deployments"]["demo"]["user"]

            commands = [
                [sys.executable, str(REPOSITORY / "installer/main.py"),
                 "install", "--module", "system-update"],
                [sys.executable, str(REPOSITORY / "installer/portable/portable_module.py"),
                 "install", "--module-dir", str(REPOSITORY / "src/system-utilities/system"),
                 "--component", "amd-gaming"],
                [sys.executable, "-c", "import sys; sys.path.insert(0,sys.argv[1]); "
                 "from remote.state import record; record('other','user','backup',None,'install')",
                 str(REPOSITORY / "installer")],
            ]
            for command in commands:
                with registry_lock(registry_path):
                    child = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        child.communicate(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        pass
                    else:
                        raise AssertionError("Mutation bypassed the held registry lock")
                stdout, stderr = child.communicate(timeout=15)
                assert child.returncode == 0, (stdout, stderr)

            profile = home / ".profile"
            target = home / "unrelated"
            original = b"keep me\n" + DEFAULT_PROFILE_LINE.encode() + b"\n"
            target.write_bytes(original)
            profile.unlink()
            profile.symlink_to(target)
            before = registry_path.read_bytes()
            try:
                uninstall(["backup", "system-update"], state, registry_path, False, home, False, False)
            except RuntimeError as error:
                assert "symbolic-link profile" in str(error)
            else:
                raise AssertionError("Symlinked profile was accepted")
            assert target.read_bytes() == original
            assert registry_path.read_bytes() == before
            assert (bin_dir / "backup-home").is_file()
            profile.unlink()
            profile.write_bytes(original)
            profile.chmod(0o640)
            uninstall(["backup", "system-update"], state, registry_path, False, home, False, False)
            assert profile.read_bytes() == b"keep me\n"
            assert profile.stat().st_mode & 0o777 == 0o640
            assert json.loads(registry_path.read_text())["remote_deployments"]
    print("Concurrency and profile safety tests passed")


if __name__ == "__main__":
    main()
