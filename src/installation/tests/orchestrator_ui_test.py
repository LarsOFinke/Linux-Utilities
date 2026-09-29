#!/usr/bin/env python3
"""Check interactive module selection and direct module setup entry points."""

from __future__ import annotations

import json
import os
import pty
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
CATALOG = json.loads((REPOSITORY / "configuration/install.json").read_text(encoding="utf-8"))["modules"]


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary) / "home"
        home.mkdir()
        environment = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(
                [str(REPOSITORY / "setup.sh"), "--no-configure"],
                cwd=REPOSITORY,
                env=environment,
                stdin=slave,
                stdout=slave,
                stderr=slave,
            )
            os.close(slave)
            slave = -1
            os.write(master, b"0\n1\n1,2\n")
            if process.wait(timeout=15) != 0:
                raise AssertionError("Interactive root setup failed")
        finally:
            if slave >= 0:
                os.close(slave)
            os.close(master)

        registry_path = home / ".local/state/shell-scripts/registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        assert set(registry["modules"]) == {"backup", "privacy"}

        before = registry_path.read_bytes()
        mixed = subprocess.run(
            [str(REPOSITORY / "setup.sh"), "--module", "backup", "--module", "ubuntu-updates"],
            env=environment,
            cwd=temporary,
            capture_output=True,
            text=True,
        )
        assert mixed.returncode != 0
        assert "different install scopes" in mixed.stderr
        assert registry_path.read_bytes() == before

        for module in ("backup", "network", "system", "privacy"):
            subprocess.run(
                [str((REPOSITORY / CATALOG[module]).parent / "setup.sh"), "--no-configure"],
                env=environment,
                cwd=temporary,
                stdout=subprocess.DEVNULL,
                check=True,
            )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        assert set(registry["modules"]) == {"backup", "network", "system", "privacy"}

        mock_bin = Path(temporary) / "bin"
        mock_bin.mkdir()
        crontab_state = Path(temporary) / "crontab"
        mock_crontab = mock_bin / "crontab"
        mock_crontab.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ "$1" == -l ]]; then exit 1; fi\n'
            'cp -- "$1" "$MOCK_CRONTAB"\n',
            encoding="utf-8",
        )
        mock_crontab.chmod(0o755)
        environment["PATH"] = f"{mock_bin}:{environment['PATH']}"
        environment["MOCK_CRONTAB"] = str(crontab_state)
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(
                [str(REPOSITORY / "src/modules/data-privacy/privacy/setup.sh")],
                cwd=REPOSITORY,
                env=environment,
                stdin=slave,
                stdout=slave,
                stderr=slave,
            )
            os.close(slave)
            slave = -1
            os.write(master, b"y\n\n\n\n\n\n")
            if process.wait(timeout=15) != 0:
                raise AssertionError("Interactive privacy setup failed")
        finally:
            if slave >= 0:
                os.close(slave)
            os.close(master)
        assert (home / ".config/privacy-cleanup/user.cfg").is_file()
        assert "privacy-cleanup user" in crontab_state.read_text(encoding="utf-8")

        vps_root = Path(temporary) / "vps-root"
        nginx_dir = vps_root / "etc/nginx"
        for name in ("sites-available", "sites-enabled", "conf.d", "snippets"):
            (nginx_dir / name).mkdir(parents=True)
        (nginx_dir / "nginx.conf").write_text(
            "http {\n    include /etc/nginx/conf.d/*.conf;\n"
            "    include /etc/nginx/sites-enabled/*;\n}\n",
            encoding="utf-8",
        )
        (nginx_dir / "sites-available/default").touch()
        (nginx_dir / "sites-enabled/default").symlink_to("../sites-available/default")
        for name, script in {
            "apt-get": "#!/bin/sh\nexit 0\n",
            "nginx": "#!/bin/sh\n[ \"$1\" = -t ]\n",
            "systemctl": "#!/bin/sh\n[ \"$1\" != is-active ]\n",
        }.items():
            path = mock_bin / name
            path.write_text(script, encoding="utf-8")
            path.chmod(0o755)
        environment["SHELL_SCRIPTS_INSTALL_ROOT"] = str(vps_root)
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(
                [str(REPOSITORY / "setup.sh"), "--module", "vps-gateway"],
                cwd=REPOSITORY,
                env=environment,
                stdin=slave,
                stdout=slave,
                stderr=slave,
            )
            os.close(slave)
            slave = -1
            os.write(master, b"y\n1\nsite.example.org\n18081\n18081\nn\ny\n")
            if process.wait(timeout=20) != 0:
                raise AssertionError("Interactive VPS gateway setup failed")
        finally:
            if slave >= 0:
                os.close(slave)
            os.close(master)
        assert (nginx_dir / "sites-enabled/site.example.org.conf").is_symlink()
        assert (nginx_dir / "sites-enabled/vps-gateway-catch-all.conf").is_symlink()
        assert not (nginx_dir / "sites-enabled/default").exists()
        print("Orchestrator UI tests passed")


if __name__ == "__main__":
    main()
