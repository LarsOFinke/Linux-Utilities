#!/usr/bin/env python3
"""Drive real local/SSH wrappers through a PTY with isolated package tools."""

from __future__ import annotations

import errno
import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]


def interact(command: list[str], environment: dict[str, str], answer: str) -> tuple[int, str]:
    master, slave = pty.openpty()
    process = subprocess.Popen(command, env=environment, cwd=REPOSITORY,
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = bytearray()
    answered = False
    deadline = time.monotonic() + 20
    try:
        while time.monotonic() < deadline:
            if not select.select([master], [], [], 0.1)[0]:
                continue
            try:
                chunk = os.read(master, 65536)
            except OSError as error:
                if error.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            output.extend(chunk)
            if b"[y/N]" in output and not answered:
                os.write(master, (answer + "\n").encode())
                answered = True
        else:
            raise AssertionError(f"Wrapper timed out: {output.decode()}")
        status = process.wait(timeout=5)
        assert answered, output.decode()
        return status, output.decode()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="dependency-wrapper-") as temporary:
        root = Path(temporary)
        tools = root / "bin"
        tools.mkdir()
        for name in ("bash", "python3", "dirname", "git"):
            executable = shutil.which(name)
            assert executable, name
            (tools / name).symlink_to(executable)
        (tools / "sudo").write_text('#!/bin/bash\n[[ "$1" == -n ]] && shift\n[[ "$1" == -- ]] && shift\nexec "$@"\n')
        # This deliberately stops at compilation: no actual packages or compiler are used.
        (tools / "apt-get").write_text(
            '#!/bin/bash\n'
            '[[ "$*" == "install -y build-essential" ]] || exit 90\n'
            'echo installed >> "$TEST_PACKAGE_LOG"\n'
            'printf "#!/bin/bash\\necho MOCK_COMPILER_REACHED >&2\\nexit 73\\n" > "$TEST_TOOLS/cc"\n'
            '/bin/chmod +x "$TEST_TOOLS/cc"\n')
        (tools / "ssh").write_text(
            '#!/bin/bash\n[[ "$1" == -o && "$2" == BatchMode=yes && "$3" == demo ]] || exit 91\n'
            'export HOME="$TEST_REMOTE_HOME"\nexec /bin/sh -c "$4"\n')
        for name in ("sudo", "apt-get", "ssh"):
            (tools / name).chmod(0o755)
        environment = dict(os.environ, PATH=str(tools), HOME=str(root / "home"),
                           TEST_TOOLS=str(tools), TEST_PACKAGE_LOG=str(root / "packages"),
                           TEST_REMOTE_HOME=str(root / "remote"), PYTHONDONTWRITEBYTECODE="1")
        environment.pop("SHELL_SCRIPTS_INSTALL_ROOT", None)
        command = [str(REPOSITORY / "main.sh"), "setup", "--module", "loc-rank", "--no-configure"]
        for remote in (False, True):
            args = [*command, "--ssh", "demo"] if remote else command
            status, output = interact(args, environment, "n")
            assert status and "not installed" in output, output
            assert not (root / "packages").exists()
            status, output = interact(args, environment, "y")
            assert status and "MOCK_COMPILER_REACHED" in output, output
            assert (root / "packages").read_text().splitlines() == ["installed"]
            assert not list(root.rglob("registry.json")), "Failed build published a registry"
            (tools / "cc").unlink()
            (root / "packages").unlink()
        result = subprocess.run(command, env=environment, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        assert result.returncode and "Noninteractive" in result.stderr, result.stderr
        assert not (root / "packages").exists()
    print("Local and remote wrapper dependency consent tests passed")


if __name__ == "__main__":
    main()
