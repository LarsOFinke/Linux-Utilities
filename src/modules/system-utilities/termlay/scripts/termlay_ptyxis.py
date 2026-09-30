"""Ptyxis terminal backend using its documented command line interface."""

from __future__ import annotations

import shutil
import subprocess

from termlay_core import Layout, TermlayError


class PtyxisBackend:
    def open_layout(self, layout: Layout) -> None:
        executable = shutil.which("ptyxis")
        if executable is None:
            raise TermlayError("Ptyxis is not installed or not on PATH")
        for directory in layout.directories:
            try:
                subprocess.run([executable, "--tab", "--working-directory", str(directory)], check=True)
            except subprocess.CalledProcessError as error:
                raise TermlayError(f"Ptyxis failed to open {directory} (exit {error.returncode})") from error
