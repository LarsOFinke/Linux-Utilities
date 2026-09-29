#!/usr/bin/env python3
"""Exercise SSH module transport and local deployment records without a network host."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]


def run(command: list[str | Path], environment: dict[str, str], success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(item) for item in command], env=environment,
                            text=True, capture_output=True, cwd=REPOSITORY)
    if success and result.returncode:
        raise AssertionError(f"{command}: {result.stderr}")
    return result


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        local = root / "local"
        remote = root / "remote"
        bin_dir = root / "bin"
        for path in (local, remote, bin_dir):
            path.mkdir()
        ssh = bin_dir / "ssh"
        ssh.write_text("#!/usr/bin/env bash\n"
                       '[[ "$1" == -o && "$2" == BatchMode=yes ]] || exit 2\n'
                       '[[ "$3" == demo ]] || exit 2\n'
                       'export HOME="$MOCK_REMOTE_HOME"\n'
                       'exec /bin/sh -c "$4"\n', encoding="utf-8")
        ssh.chmod(0o755)
        sudo = bin_dir / "sudo"
        sudo.write_text("#!/usr/bin/env bash\n"
                        '[[ "$1" == -n && "$2" == -- ]] || exit 2\n'
                        'shift 2\nexec "$@"\n', encoding="utf-8")
        sudo.chmod(0o755)
        environment = dict(os.environ, HOME=str(local), MOCK_REMOTE_HOME=str(remote),
                           PATH=f"{bin_dir}:{os.environ['PATH']}", PYTHONDONTWRITEBYTECODE="1")
        registry = local / ".local/state/shell-scripts/registry.json"
        remote_bin = remote / ".local/bin"
        remote_system = root / "remote-system"
        environment["SHELL_SCRIPTS_INSTALL_ROOT"] = str(remote_system)

        run([REPOSITORY / "setup.sh", "--ssh", "demo", "--module", "system-update"], environment)
        run([REPOSITORY / "setup.sh", "--ssh", "demo", "--component", "system:amd-gaming"], environment)
        run([REPOSITORY / "setup.sh", "--ssh", "demo", "--module", "network"], environment)
        assert (remote_bin / "update-system").is_file()
        assert (remote_bin / "install-amd-gaming").is_file()
        assert (remote_bin / "capture-traffic").is_file()
        assert (remote_bin / "capture_registry.py").is_file()
        record = json.loads(registry.read_text(encoding="utf-8"))
        assert not record["modules"]
        assert set(record["remote_deployments"]["demo"]["user"]) == {"system-update", "system", "network"}
        assert record["remote_deployments"]["demo"]["user"]["system"]["components"] == ["amd-gaming"]
        run([REPOSITORY / "setup.sh", "--ssh", "demo", "--module", "ubuntu-updates"], environment)
        assert (remote_system / "usr/local/bin/ubuntu-updates").is_file()
        assert "ubuntu-updates" in json.loads(registry.read_text(encoding="utf-8"))["remote_deployments"]["demo"]["system"]
        listing = run([REPOSITORY / "uninstall.sh", "--ssh", "demo", "--list"], environment).stdout
        assert "system:amd-gaming" in listing and "system-update [user]" in listing
        assert "ubuntu-updates [system]" in listing
        record = json.loads(registry.read_text(encoding="utf-8"))
        del record["remote_deployments"]["demo"]["user"]["network"]
        registry.write_text(json.dumps(record), encoding="utf-8")
        listing = run([REPOSITORY / "uninstall.sh", "--ssh", "demo", "--list"], environment).stdout
        assert "network [user]" in listing and "not in local deployment registry" in listing

        command = remote_bin / "update-system"
        original = command.read_bytes()
        command.write_bytes(original + b"# local change\n")
        failed = run([REPOSITORY / "uninstall.sh", "--ssh", "demo", "--module", "system-update"],
                     environment, success=False)
        assert failed.returncode and command.exists()
        assert "system-update" in json.loads(registry.read_text(encoding="utf-8"))["remote_deployments"]["demo"]["user"]
        command.write_bytes(original)
        run([REPOSITORY / "uninstall.sh", "--ssh", "demo", "--component", "system:amd-gaming"], environment)
        assert not (remote_bin / "install-amd-gaming").exists()
        assert command.exists()
        run([REPOSITORY / "uninstall.sh", "--ssh", "demo", "--module", "network"], environment)
        assert not (remote_bin / "capture-traffic").exists()
        run([REPOSITORY / "uninstall.sh", "--ssh", "demo", "--module", "system-update"], environment)
        assert not command.exists()
        run([REPOSITORY / "uninstall.sh", "--ssh", "demo", "--module", "ubuntu-updates"], environment)
        assert not (remote_system / "usr/local/bin/ubuntu-updates").exists()
        assert not json.loads(registry.read_text(encoding="utf-8"))["remote_deployments"]
    print("Remote deployment tests passed")


if __name__ == "__main__":
    main()
