"""Open saved layouts with Ptyxis."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from Layout import Layout
from TermlayError import TermlayError


class PtyxisBackend:
    def current_shell(self) -> str | None:
        """Reuse only a foreground, interactive terminal belonging to Ptyxis."""
        if not os.environ.get("PTYXIS_VERSION") or not sys.stdin.isatty() or not sys.stdout.isatty():
            return None
        if os.environ.get("TMUX") or os.environ.get("STY") or os.environ.get("SSH_CONNECTION"):
            return None
        try:
            if os.tcgetpgrp(sys.stdin.fileno()) != os.getpgrp():
                return None
        except OSError:
            return None
        shell = shutil.which(os.environ.get("SHELL") or "/bin/sh")
        if shell is None:
            raise TermlayError("the current shell is not executable; set SHELL or use --new-tabs")
        return shell

    def open_layout(self, layout: Layout, new_tabs: bool = False) -> None:
        executable = shutil.which("ptyxis")
        if executable is None:
            raise TermlayError("Ptyxis is not installed or not on PATH")
        shell = None if new_tabs else self.current_shell()
        directories = layout.directories[1:] if shell else layout.directories
        for directory in directories:
            try:
                subprocess.run([executable, "--tab", "--working-directory", str(directory)], check=True)
            except subprocess.CalledProcessError as error:
                raise TermlayError(f"Ptyxis failed to open {directory} (exit {error.returncode})") from error
        if shell:
            previous = os.getcwd()
            environment = dict(os.environ, PWD=str(layout.directories[0]), OLDPWD=previous)
            try:
                os.chdir(layout.directories[0])
                sys.stdout.flush()
                sys.stderr.flush()
                os.execvpe(shell, [shell, "-i"], environment)
            except OSError as error:
                os.chdir(previous)
                raise TermlayError(f"cannot start shell in {layout.directories[0]}: {error}") from error
