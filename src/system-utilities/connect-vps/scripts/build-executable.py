#!/usr/bin/env python3
"""Build a single Linux executable containing this module's Python sources."""

from __future__ import annotations

import io
import os
import subprocess
import sys
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
    args[2] = "import runpy,sys; p=sys.argv.pop(1); sys.argv[0]=p; runpy.run_path(p,run_name='__main__')";
    args[3] = path;
    for (int index = 1; index < argc; ++index)
        args[index + 3] = argv[index];
    execvp(args[0], args);
    perror("execvp python3");
    return 1;
}
'''


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build-executable.py OUTPUT")
    scripts = Path(__file__).resolve().parent
    output = Path(sys.argv[1])
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(scripts / "connect-vps", "__main__.py")
        for source in sorted(scripts.rglob("*.py")):
            if source.name != "build-executable.py":
                bundle.write(source, source.relative_to(scripts).as_posix())
    subprocess.run(["cc", "-O2", "-std=c99", "-x", "c", "-", "-o", str(output)],
                   input=LAUNCHER.encode(), check=True)
    with output.open("ab") as executable:
        executable.write(archive.getvalue())
    os.chmod(output, 0o755)


if __name__ == "__main__":
    main()
