#!/usr/bin/env python3
"""Check scheduled entry points migrate before old binaries are removed."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from portable.portable_support import migration

REPOSITORY = Path(__file__).resolve().parents[3]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        cron = root / "etc/cron.d/privacy-cleanup"
        cron.parent.mkdir(parents=True)
        cron.write_text("# managed by shell-scripts privacy\n17 3 * * * root "
                        "/usr/local/bin/privacy-scheduled --system\n")
        old = {"privacy-scheduled": {}}
        assert migration.files("privacy", old, root, True) == [cron]
        assert migration.apply("privacy", old, root, True, None)
        assert "/usr/local/bin/privacy --system scheduled" in cron.read_text()

        mock_bin = root / "mock-bin"
        mock_bin.mkdir()
        crontab = mock_bin / "crontab"
        crontab.write_text("#!/bin/sh\nif [ \"$1\" = -l ]; then cat \"$MOCK_CRONTAB\"; "
                           "else cat > \"$MOCK_CRONTAB\"; fi\n")
        crontab.chmod(0o755)
        saved_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{mock_bin}:{saved_path}"
        os.environ["MOCK_CRONTAB"] = str(root / "user-crontab")
        user_cron = root / "user-crontab"
        user_cron.write_text("17 3 * * * /home/test/.local/bin/privacy-scheduled # privacy-cleanup user\n")
        try:
            original = migration.user_crontab("privacy", old, False)
            assert migration.apply("privacy", old, root, False, original)
            assert "/privacy scheduled # privacy-cleanup user" in user_cron.read_text()
            migration.restore_crontab(original)
            assert "privacy-scheduled" in user_cron.read_text()
        finally:
            os.environ["PATH"] = saved_path
            del os.environ["MOCK_CRONTAB"]

        state = root / "var/lib/shell-scripts/canary"
        units = root / "etc/systemd/system"
        state.mkdir(parents=True)
        units.mkdir(parents=True)
        record = state / "demo.json"
        unit = units / "fs-file-monitor-demo.service"
        unit.write_text("ExecStart=/usr/local/bin/fs-tracker --config /etc/fs-tracker/demo.conf\n")
        record.write_text(json.dumps({"name": "demo", "unit_sha256": digest(unit)}))
        ssh_record = state / "ssh/record.json"
        ssh_record.parent.mkdir()
        ssh_unit = units / "fs-ssh-watch.service"
        ssh_unit.write_text("ExecStart=/usr/local/bin/canary-ssh-watcher --config /etc/fs-tracker/ssh-watch.json\n")
        ssh_record.write_text(json.dumps({"kind": "ssh", "unit_sha256": digest(ssh_unit)}))
        old = {"fs-tracker": {}, "canary-ssh-watcher": {}}
        assert len(migration.files("canary", old, root, True)) == 4
        assert migration.apply("canary", old, root, True, None)
        assert "canary tracker --config" in unit.read_text()
        assert "canary ssh-watch --config" in ssh_unit.read_text()
        assert json.loads(record.read_text())["unit_sha256"] == digest(unit)
        assert json.loads(ssh_record.read_text())["unit_sha256"] == digest(ssh_unit)
        unit.write_text("# local edit\n")
        try:
            migration.files("canary", old, root, True)
        except RuntimeError as error:
            assert "changed" in str(error)
        else:
            raise AssertionError("Locally edited service was accepted")
    update_cleanup()
    print("Scheduled command migrations passed")


def update_cleanup() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        home = root / "home"
        home.mkdir()
        mock_bin = root / "mock-bin"
        mock_bin.mkdir()
        crontab = mock_bin / "crontab"
        crontab.write_text("#!/bin/sh\nif [ \"$1\" = -l ]; then cat \"$MOCK_CRONTAB\"; "
                           "else cat > \"$MOCK_CRONTAB\"; fi\n")
        crontab.chmod(0o755)
        user_cron = root / "user-crontab"
        user_cron.write_text(f"17 3 * * * {home}/.local/bin/privacy-scheduled # privacy-cleanup user\n")
        env = dict(os.environ, HOME=str(home), MOCK_CRONTAB=str(user_cron),
                   PATH=f"{mock_bin}:{os.environ['PATH']}", PYTHONDONTWRITEBYTECODE="1")
        command = REPOSITORY / "installer/main.py"

        def run(*args: str, environment: dict[str, str] = env) -> None:
            subprocess.run([sys.executable, str(command), *args], env=environment,
                           check=True, capture_output=True, text=True)

        run("install", "--module", "privacy")
        registry = home / ".local/state/shell-scripts/registry.json"
        installed = home / ".local/bin"
        data = json.loads(registry.read_text())
        old = installed / "privacy-scheduled"
        old.write_bytes(b"previous executable")
        data["modules"]["privacy"]["commands"][old.name] = {
            "path": str(old), "sha256": digest(old), "source": str(command)}
        registry.write_text(json.dumps(data))
        run("update", "--module", "privacy")
        assert not old.exists() and (installed / "privacy").is_file()
        assert "privacy scheduled # privacy-cleanup user" in user_cron.read_text()

        system_root = root / "system-root"
        system_env = dict(env, SHELL_SCRIPTS_INSTALL_ROOT=str(system_root))
        run("install", "--system", "--module", "canary", environment=system_env)
        registry = system_root / "var/lib/shell-scripts/registry.json"
        installed = system_root / "usr/local/bin"
        data = json.loads(registry.read_text())
        for name in ("fs-tracker", "canary-ssh-watcher"):
            old = installed / name
            old.write_bytes(b"previous executable")
            data["modules"]["canary"]["commands"][name] = {
                "path": str(old), "sha256": digest(old), "source": str(command)}
        registry.write_text(json.dumps(data))
        state = system_root / "var/lib/shell-scripts/canary"
        unit = system_root / "etc/systemd/system/fs-file-monitor-demo.service"
        state.mkdir(parents=True)
        unit.parent.mkdir(parents=True)
        unit.write_text("ExecStart=/usr/local/bin/fs-tracker --config /etc/fs-tracker/demo.conf\n")
        (state / "demo.json").write_text(json.dumps({"name": "demo", "unit_sha256": digest(unit)}))
        run("update", "--system", "--module", "canary", environment=system_env)
        assert all(not (installed / name).exists() for name in ("fs-tracker", "canary-ssh-watcher"))
        assert "canary tracker --config" in unit.read_text()
        assert json.loads((state / "demo.json").read_text())["unit_sha256"] == digest(unit)


if __name__ == "__main__":
    main()
