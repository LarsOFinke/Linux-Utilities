#!/usr/bin/env python3
"""Inject interruption and publication failures without touching the host."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import subprocess
from types import SimpleNamespace

from catalog import MODULES, REPOSITORY
from core.registry import paths
from setup.install import install as shared_install
from uninstall.remove import uninstall as shared_uninstall
from setup import install as install_logic
from uninstall import remove as remove_logic


def portable_helper(module: str):
    path = REPOSITORY / "installer/portable/portable_module.py"
    spec = importlib.util.spec_from_file_location("portable_recovery", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.configure((REPOSITORY / MODULES[module]["manifest"]).parent)
    return helper


def snapshot(home: Path) -> dict:
    return {str(path.relative_to(home)): (path.read_bytes(), path.stat().st_mode & 0o777)
            for path in home.rglob("*") if path.is_file() and path.name != "registry.lock"}


def expect_failure(call, failure):
    try:
        call()
    except type(failure) as error:
        assert error is failure
    else:
        raise AssertionError("Expected injected failure")


def install_recovery(portable: bool, existing: bool, failure: BaseException) -> None:
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, HOME=temporary):
        home = Path(temporary)
        helper = portable_helper("backup") if portable else SimpleNamespace(
            paths=paths, install=shared_install, copy_command=install_logic.copy_command
        )
        if portable:
            bin_dir, state, root = helper.locations(False)
            install = lambda: helper.install(bin_dir, state, root, False)
            copy_name = "atomic_copy"
        else:
            bin_dir, state, _ = helper.paths(False)
            install = lambda: helper.install(["backup"], {}, bin_dir, state, False)
            copy_name = "copy_command"
        if existing:
            install()
        before = snapshot(home)
        copy_owner = helper.install_logic if portable else install_logic
        real_copy = getattr(copy_owner, copy_name)

        def interrupted_copy(source, target, executable):
            real_copy(source, target, executable)
            target.write_bytes(b"partially upgraded command\n")
            raise failure

        with patch.object(copy_owner, copy_name, interrupted_copy):
            expect_failure(install, failure)
        assert snapshot(home) == before
        install()  # No unmanaged remnants should block a retry.


def uninstall_recovery(portable: bool, publication: bool, failure: BaseException) -> None:
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, HOME=temporary):
        home = Path(temporary)
        helper = portable_helper("privacy") if portable else SimpleNamespace(paths=paths, install=shared_install, uninstall=shared_uninstall, subprocess=subprocess)
        if portable:
            bin_dir, state, root = helper.locations(False)
            helper.install(bin_dir, state, root, False)
            uninstall = lambda: helper.uninstall(state, helper.read_state(state, False), False, False, False, root)
        else:
            bin_dir, state, root = helper.paths(False)
            helper.install(["privacy"], {}, bin_dir, state, False)
            uninstall = lambda: helper.uninstall(["privacy"], {}, state, False, root, False, False)
        # Preserve local file modes as well as bytes during recovery.
        (bin_dir / "privacy-status").chmod(0o700)
        before = snapshot(home)
        real_unlink = Path.unlink
        deleted = 0

        def failing_unlink(path, *args, **kwargs):
            nonlocal deleted
            result = real_unlink(path, *args, **kwargs)
            if path.parent == bin_dir:
                deleted += 1
            if (publication and portable and path == state) or (not publication and deleted == 2):
                deleted = -100  # One-shot failure; rollback must be allowed to run.
                raise failure
            return result

        def failed_publication(*args):
            raise failure

        # The hook is deliberately mocked: these tests check command/state recovery.
        with patch.object(helper.subprocess, "run") as hook:
            with patch.object(Path, "unlink", failing_unlink):
                if publication and not portable:
                    with patch.object(remove_logic, "atomic_json", failed_publication):
                        expect_failure(uninstall, failure)
                else:
                    expect_failure(uninstall, failure)
            assert snapshot(home) == before
            uninstall()
            assert hook.call_count == 2
        assert not any(bin_dir.iterdir())


def main() -> None:
    for portable in (False, True):
        for error in (OSError, KeyboardInterrupt):
            for existing in (False, True):
                install_recovery(portable, existing, error("injected copy failure"))
            for publication in (False, True):
                uninstall_recovery(portable, publication, error("injected removal failure"))
    print("Shared and portable recovery tests passed")


if __name__ == "__main__":
    main()
