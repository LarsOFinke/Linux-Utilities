"""Match a Ptyxis foreground command to its owning shell directory."""

from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

SHELLS = {"bash", "zsh", "fish", "sh", "dash"}


def _resolved_argument(value: str, process: Path) -> Path | None:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute() and "/" not in value:
        located = shutil.which(value)
        if located is None:
            return None
        candidate = Path(located)
    elif not candidate.is_absolute():
        try:
            candidate = process.joinpath("cwd").resolve(strict=True) / candidate
        except (OSError, RuntimeError):
            return None
    try:
        return candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def _command_match(title: list[str], argv: list[str], process: Path) -> int:
    """Rank exact title matches and common interpreter-launched binaries."""
    if argv == title:
        return 3
    for candidate in (argv, argv[1:]):
        if len(candidate) < len(title):
            continue
        for index, (expected, actual) in enumerate(zip(title, candidate)):
            if expected == actual or (index == 0 and Path(expected).name == Path(actual).name):
                continue
            # Compare launcher aliases without discarding script paths/arguments.
            if index > 0 and ("/" not in expected or "/" not in actual):
                break
            expected_path = _resolved_argument(expected, process)
            if expected_path is None or expected_path != _resolved_argument(actual, process):
                break
        else:
            return 2
    return 0


def _owned_directories(process: Path, proc_root: Path) -> tuple[Path | None, Path | None] | None:
    foreground_process = process
    shell = None
    visited = set()
    while process.name not in visited:
        visited.add(process.name)
        try:
            comm = process.joinpath("comm").read_text(encoding="utf-8").strip()
            if comm == "ptyxis-agent":
                if shell is None:
                    return None
                shell_directory = shell.joinpath("cwd").resolve(strict=True)
                try:
                    process_directory = foreground_process.joinpath("cwd").resolve(strict=True)
                except (OSError, RuntimeError):
                    process_directory = None
                return shell_directory, process_directory
            if comm in SHELLS:
                shell = process
            status = process.joinpath("status").read_text(encoding="utf-8")
            parent = next(int(line.split()[1]) for line in status.splitlines() if line.startswith("PPid:"))
        except (OSError, RuntimeError, StopIteration, ValueError):
            return None
        if parent <= 1:
            return None
        process = proc_root / str(parent)
    return None


def _directory_from_tab_title(title: str, directories: list[Path]) -> str | None:
    """Disambiguate matching commands using the tab's displayed workspace label."""
    label = title.rsplit(" — ", 1)[0].rsplit(" | ", 1)[-1].strip()
    matches = {directory for directory in directories if directory.name == label}
    return str(next(iter(matches))) if len(matches) == 1 else None


def foreground_directory(title: str, proc_root: Path = Path("/proc")) -> str | None:
    if " — " not in title:
        return None
    try:
        command = shlex.split(title.rsplit(" — ", 1)[1])
    except ValueError:
        return None
    if not command:
        return None

    matches: list[tuple[int, Path, tuple[Path | None, Path | None] | None]] = []
    for process in proc_root.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            argv = [os.fsdecode(part) for part in process.joinpath("cmdline").read_bytes().split(b"\0") if part]
        except OSError:
            continue
        if argv:
            score = _command_match(command, argv, process)
            if score:
                directories = _owned_directories(process, proc_root)
                matches.append((score, process, directories))
    if not matches:
        return None
    best_score = max(score for score, _, _ in matches)
    best_matches = [(process, directories) for score, process, directories in matches
                    if score == best_score]
    owned = [directories for _, directories in best_matches if directories is not None]
    if len(owned) == 1:
        shell_directory, process_directory = owned[0]
        directory = process_directory or shell_directory
    elif not owned and len(best_matches) == 1:
        # Some terminal launchers hide or reparent the shell/agent chain. A
        # unique same-user command match still has a trustworthy /proc cwd.
        try:
            directory = best_matches[0][0].joinpath("cwd").resolve(strict=True)
        except (OSError, RuntimeError):
            return None
    else:
        # Only inspect directories of matching Ptyxis commands: unrelated idle
        # shells with a similar directory name do not identify this tab.
        directories = [foreground or shell for shell, foreground in owned]
        return _directory_from_tab_title(title, [path for path in directories if path is not None])
    return str(directory) if directory is not None else None
