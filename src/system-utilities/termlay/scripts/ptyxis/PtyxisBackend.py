"""Open saved layout directories as Ptyxis tabs."""

from __future__ import annotations

import shutil
import subprocess

from Layout import Layout
from TermlayError import TermlayError


class PtyxisBackend:
    def open_layout(self, layout: Layout, new_window: bool = False) -> None:
        executable = shutil.which("ptyxis")
        if executable is None:
            raise TermlayError("Ptyxis is not installed or not on PATH")
        for index, directory in enumerate(layout.directories):
            placement = "--new-window" if new_window and index == 0 else "--tab"
            try:
                subprocess.run([executable, placement, "--working-directory", str(directory)], check=True)
            except subprocess.CalledProcessError as error:
                raise TermlayError(
                    f"Ptyxis failed to open {directory} (exit {error.returncode})"
                ) from error
