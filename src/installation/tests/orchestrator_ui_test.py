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
            os.write(master, b"0\n1,4\n")
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
                [str(REPOSITORY / "src" / module / "setup.sh"), "--no-configure"],
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
                [str(REPOSITORY / "src/privacy/setup.sh")],
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
        print("Orchestrator UI tests passed")


if __name__ == "__main__":
    main()
