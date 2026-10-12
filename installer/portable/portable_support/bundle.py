"""Build one Linux executable for a command and its nearby runtime files.

The executable carries a ZIP payload and launches the embedded command from a
private temporary directory. This keeps shell sourcing and sibling command
lookups working without installing helper files beside the command.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import zipfile
from pathlib import Path


LAUNCHER = r'''
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char path[4096];
    ssize_t length = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (length < 0 || length == sizeof(path) - 1) {
        perror("readlink /proc/self/exe");
        return 1;
    }
    path[length] = '\0';
    char **args = calloc((size_t)argc + 5, sizeof(char *));
    if (args == NULL) {
        perror("calloc");
        return 1;
    }
    args[0] = "python3";
    args[1] = "-c";
    args[2] = "import runpy,sys; p=sys.argv.pop(1); runpy.run_path(p,run_name='__main__')";
    args[3] = path;
    args[4] = __COMMAND__;
    for (int index = 1; index < argc; ++index)
        args[index + 4] = argv[index];
    execvp(args[0], args);
    perror("execvp python3");
    return 1;
}
'''


def build(command: str, files: dict[str, Path], executable: set[str], output: Path) -> None:
    """Compile a launcher with a flat, module-owned runtime bundle."""
    if command not in executable or any("/" in name or name in (".", "..") for name in files):
        raise ValueError(f"Invalid bundled command or file name: {command}")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        runtime = zipfile.ZipInfo("__main__.py")
        runtime.external_attr = 0o644 << 16
        bundle.writestr(runtime, Path(__file__).with_name("bundle_runtime.py").read_bytes(),
                        compress_type=zipfile.ZIP_DEFLATED)
        for name, source in sorted(files.items()):
            info = zipfile.ZipInfo(name)
            info.external_attr = ((0o755 if name in executable else 0o644) << 16)
            bundle.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    subprocess.run(["cc", "-O2", "-std=c99", "-x", "c", "-", "-o", str(output)],
                   input=LAUNCHER.replace("__COMMAND__", json.dumps(command)).encode(), check=True)
    with output.open("ab") as stream:
        stream.write(archive.getvalue())
    os.chmod(output, 0o755)
