# Terminal layouts (`termlay`)

Save a named, ordered set of working directories and reopen them as Ptyxis tabs:

```bash
termlay save work ~/dev/frontend ~/dev/backend
termlay save-current work
termlay update
termlay open work
termlay list
termlay show work
termlay delete work
```

`termlay save work .` saves the current directory. `termlay save-current work` discovers tabs in the focused Ptyxis window in their visible order. It reads standard shell titles, and for a uniquely identifiable local foreground process (including Codex) it reads the owning shell's working directory. If a tab cannot be identified, it asks for that tab's directory; entering a blank line cancels without saving. `save-current` needs Python GObject and AT-SPI bindings plus a working desktop accessibility service. Paths are expanded, resolved to absolute directories, and checked when saved. `save` and `save-current` create new layouts and refuse to overwrite an existing name. Use `termlay update` to interactively select saved layouts, confirm replacement, and refresh them from the focused Ptyxis window. Unclear tab directories use the same prompts as `save-current`; cancelling selection or tab discovery leaves selected layouts unchanged. `open` checks **all** saved directories before starting Ptyxis and reports any that are missing. The short aliases are `s`, `o`, `ls`, and `rm`. Run `termlay --help` or `termlay --version` for CLI details.

Layouts are JSON files at `$XDG_CONFIG_HOME/termlay/layouts/<name>.json`, or `~/.config/termlay/layouts/<name>.json` when `XDG_CONFIG_HOME` is unset. `XDG_CONFIG_HOME` must be absolute. The layout directory is private (mode 0700), cannot be a symbolic link, and new files use mode 0600. The versioned file records a name and an ordered `tabs` array with each tab's `cwd`.

When run interactively in a Ptyxis tab, `open` reuses that tab for the first saved
directory and creates new tabs only for the remaining directories. A one-directory
layout therefore creates no extra tab. The reused tab starts a fresh interactive
`$SHELL` (or `/bin/sh` when unset); exiting it returns to the shell that launched
Termlay. Other existing tabs remain open. Tab reuse requires `PTYXIS_VERSION`,
terminal input/output, and a foreground process; SSH, tmux, and screen sessions
use new tabs instead. `termlay open work --new-tabs` explicitly opens every entry
in a new tab, as do noninteractive calls or calls from another terminal emulator.

Install with `./setup.sh --module termlay` from the repository root, or run this module's `setup.sh` directly. The default install puts `termlay` and its Python helpers in `~/.local/bin`; `--system` is available for a shared command. Python 3.9 or newer is required for setup and runtime. Ptyxis must be installed and available on `PATH` for `open`; saving and inspecting layouts do not need it. The backend invokes the supported `ptyxis --tab --working-directory DIR` CLI for each new tab, in order. If Ptyxis is not already running, its `--tab` option starts an instance. Installed commands work from any working directory.

`termlay` stores and reopens directories. `save-current` discovers tabs only in the focused Ptyxis window; it does not inspect other windows. Commands, shell state, and terminal window placement are not saved. An `open` operation can leave earlier tabs open if Ptyxis fails on a later tab. The origin tab's shell starts only after all requested new tabs have opened successfully; a failure leaves the calling shell available.

Remove the command with `./uninstall.sh --module termlay` or this module's `uninstall.sh`. Saved layouts are user data and remain on disk.

The scripts keep each class in its own PascalCase file. `scripts/layout/` owns layout data, storage, and path validation; `scripts/ptyxis/` owns tab discovery, process lookup, capture prompts, and opening tabs. The manifest installs their helpers beside `termlay` so the command works from any directory.

Run `python3 src/modules/system-utilities/termlay/tests/TermlayTest.py` for focused CLI and storage tests. Tests use fake Ptyxis/shell executables, a temporary home, and a real pseudo-terminal to check tab reuse; they do not open terminal windows.
