"""Read tab titles in the focused Ptyxis window through AT-SPI."""

from __future__ import annotations

from TermlayError import TermlayError


def read_current_tab_titles() -> list[str]:
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
    except (ImportError, ValueError) as error:
        raise TermlayError("save-current requires Python GObject and AT-SPI bindings") from error

    def descendants(item):
        for child in item:
            yield child
            yield from descendants(child)

    try:
        applications = [app for app in Atspi.get_desktop(0)
                        if app.get_name().casefold() == "ptyxis"]
        windows = [window for app in applications for window in app
                   if window.get_role() == Atspi.Role.FRAME
                   and window.get_state_set().contains(Atspi.StateType.ACTIVE)]
        if len(windows) != 1:
            raise TermlayError("focus the Ptyxis window to save, then run save-current in one of its tabs")
        tab_lists = [[item for item in descendants(candidate)
                      if item.get_role() == Atspi.Role.PAGE_TAB]
                     for candidate in descendants(windows[0])
                     if candidate.get_role() == Atspi.Role.PAGE_TAB_LIST]
        tab_lists = [tabs for tabs in tab_lists if tabs]
        if len(tab_lists) != 1:
            raise TermlayError("cannot determine the focused Ptyxis window's tab order")
        return [tab.get_name() for tab in tab_lists[0]]
    except TermlayError:
        raise
    except Exception as error:
        raise TermlayError(f"cannot read Ptyxis tabs through accessibility: {error}") from error
