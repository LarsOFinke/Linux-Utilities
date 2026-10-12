"""Run a bundled command from private temporary storage."""

from __future__ import annotations

import signal
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main() -> int:
    bundle = Path(sys.argv[0])
    command = sys.argv[1]
    with tempfile.TemporaryDirectory(prefix="linux-utilities-") as directory:
        root = Path(directory)
        with zipfile.ZipFile(bundle) as archive:
            archive.extractall(root)
            for entry in archive.infolist():
                (root / entry.filename).chmod((entry.external_attr >> 16) & 0o777)
        environment = dict(os.environ, LINUX_UTILITIES_BUNDLE_PATH=str(bundle))
        child = subprocess.Popen([str(root / command), *sys.argv[2:]], env=environment)
        previous = {name: signal.signal(name, lambda signum, frame: child.send_signal(signum))
                    for name in (signal.SIGINT, signal.SIGTERM)}
        try:
            status = child.wait()
        finally:
            for name, handler in previous.items():
                signal.signal(name, handler)
    return status if status >= 0 else 128 - status


if __name__ == "__main__":
    raise SystemExit(main())
