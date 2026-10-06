#!/usr/bin/env python3
"""Run the repository's isolated checks; never invoke live utility workflows."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]


def main() -> int:
    required = ("bash", "shellcheck", "cc", "git", "tar", "bzip2", "flock", "timeout", "apt-config")
    missing = [command for command in required if shutil.which(command) is None]
    if missing:
        print(f"Missing verification tools: {', '.join(missing)}", file=sys.stderr)
        return 1
    os.chdir(REPOSITORY)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PYTHONPATH=str(REPOSITORY / "src/monitoring/canary"))
    failures = []
    # Parse without creating bytecode or importing host-changing entry points.
    for path in sorted(Path("src").rglob("*.py")) + sorted(Path("installer").rglob("*.py")):
        try:
            ast.parse(path.read_bytes(), filename=str(path), feature_version=(3, 9))
        except SyntaxError as error:
            print(error, file=sys.stderr)
            failures.append(str(path))
    shells = (sorted(path for path in Path("src").rglob("*.sh") if not path.is_symlink())
              + sorted(Path("installer").rglob("*.sh"))
              + sorted(Path("scripts").glob("*.sh"))
              + [Path("main.sh")])
    commands = [(f"Bash syntax: {path}", ["bash", "-n", str(path)]) for path in shells]
    commands.append(("ShellCheck", ["shellcheck", *map(str, shells)]))
    commands.extend((str(path), ["bash", str(path)])
                    for path in sorted(path for path in Path("src").rglob("*.sh") if "tests" in path.parts)
                    + sorted(Path("installer/tests").rglob("*.sh")))
    commands.extend((str(path), [sys.executable, str(path)])
                    for path in sorted(Path("installer/tests").rglob("*_test.py")))
    for path in ("src/system-utilities/termlay/tests/TermlayTest.py",
                 "src/system-utilities/connect-vps/tests/ConnectVpsTest.py",
                 "src/monitoring/log-scout/tests/LogScoutTest.py"):
        commands.append((path, [sys.executable, path]))
    for concern in ("lifecycle", "tools"):
        commands.append((f"Canary {concern} Python", [sys.executable, "-m", "unittest", "discover",
                       "-s", f"src/monitoring/canary/tests/{concern}", "-p", "*Test*.py"]))
    for name, command in commands:
        print(f"\n>>> {name}", flush=True)
        if subprocess.run(command, env=environment, check=False).returncode:
            failures.append(name)
    if failures:
        print(f"\nFailed checks: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"\nAll {len(commands)} check commands and Python 3.9 syntax checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
