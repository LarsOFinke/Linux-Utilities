"""Resolve visible Ptyxis tabs to directories, asking when needed."""

from __future__ import annotations

import re

from Layout import Layout
from TermlayError import TermlayError
from layout_paths import resolve_directory, validate_name
from process_directory import foreground_directory
from ptyxis_tabs import read_current_tab_titles

SHELL_TITLE = re.compile(r"[^@\s:]+@[^:\s]+: (~/.*|/.*|~)\Z")


def directory_from_title(title: str) -> str | None:
    match = SHELL_TITLE.fullmatch(title.rsplit(" — ", 1)[0])
    return match.group(1) if match else None


def current_layout(name: str) -> Layout:
    validate_name(name)
    directories = []
    for index, title in enumerate(read_current_tab_titles(), 1):
        directory = directory_from_title(title) or foreground_directory(title)
        while True:
            if directory is not None:
                try:
                    resolved = resolve_directory(directory)
                    break
                except TermlayError:
                    directory = None
            try:
                directory = input(f"Directory for tab {index} {title!r} (blank cancels): ").strip()
            except EOFError as error:
                raise TermlayError(f"cannot determine directory for tab {index}; no layout saved") from error
            if not directory:
                raise TermlayError(f"directory for tab {index} was not provided; no layout saved")
        directories.append(resolved)
    if not directories:
        raise TermlayError("no Ptyxis tabs found; no layout saved")
    return Layout(name, tuple(directories))
