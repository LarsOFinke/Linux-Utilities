"""Match a Ptyxis foreground command to its owning shell directory."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

SHELLS = {"bash", "zsh", "fish", "sh", "dash"}


def foreground_directory(title: str, proc_root: Path = Path("/proc")) -> str | None:
    if " — " not in title:
        return None
    try:
        command = shlex.split(title.rsplit(" — ", 1)[1])
    except ValueError:
        return None
    if not command:
        return None

    matches = []
    for process in proc_root.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            argv = [os.fsdecode(part) for part in process.joinpath("cmdline").read_bytes().split(b"\0") if part]
        except OSError:
            continue
        if argv and Path(argv[0]).name == Path(command[0]).name and argv[1:] == command[1:]:
            matches.append(process)
    if len(matches) != 1:
        return None

    process = matches[0]
    shell = None
    visited = set()
    while process.name not in visited:
        visited.add(process.name)
        try:
            comm = process.joinpath("comm").read_text(encoding="utf-8").strip()
            if comm == "ptyxis-agent":
                return str(shell.joinpath("cwd").resolve()) if shell is not None else None
            if comm in SHELLS:
                shell = process
            status = process.joinpath("status").read_text(encoding="utf-8")
            parent = next(int(line.split()[1]) for line in status.splitlines() if line.startswith("PPid:"))
        except (OSError, StopIteration, ValueError):
            return None
        if parent <= 1:
            return None
        process = proc_root / str(parent)
    return None
