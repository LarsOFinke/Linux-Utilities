# Terminal layouts (`termlay`)

Save a named, ordered set of working directories and reopen them as Ptyxis tabs:

```bash
termlay save work ~/dev/frontend ~/dev/backend
termlay save-current work
termlay open work
termlay list
termlay show work
termlay delete work
```

`termlay save work .` saves the current directory. `termlay save-current work` discovers tabs in the focused Ptyxis window in their visible order. It reads standard shell titles, and for a uniquely identifiable local foreground process (including Codex) it reads the owning shell's working directory. If a tab cannot be identified, it asks for that tab's directory; entering a blank line cancels without saving. `save-current` needs Python GObject and AT-SPI bindings plus a working desktop accessibility service. Paths are expanded, resolved to absolute directories, and checked when saved. An existing name requires `--force` to overwrite it, including with `save-current`. `open` checks **all** saved directories before starting Ptyxis and reports any that are missing. The short aliases are `s`, `o`, `ls`, and `rm`. Run `termlay --help` or `termlay --version` for CLI details.

Layouts are JSON files at `$XDG_CONFIG_HOME/termlay/layouts/<name>.json`, or `~/.config/termlay/layouts/<name>.json` when `XDG_CONFIG_HOME` is unset. `XDG_CONFIG_HOME` must be absolute. The layout directory is private (mode 0700), cannot be a symbolic link, and new files use mode 0600. The versioned file records a name and an ordered `tabs` array with each tab's `cwd`.

Install with `./setup.sh --module termlay` from the repository root, or run this module's `setup.sh` directly. The default install puts `termlay` and its Python helpers in `~/.local/bin`; `--system` is available for a shared command. Python 3.9 or newer is required for setup and runtime. Ptyxis must be installed and available on `PATH` for `open`; saving and inspecting layouts do not need it. The backend invokes the supported `ptyxis --tab --working-directory DIR` CLI once per directory, in order. If Ptyxis is not already running, its `--tab` option starts an instance. Installed commands work from any working directory.

`termlay` stores and reopens directories. `save-current` discovers tabs only in the focused Ptyxis window; it does not inspect other windows. Commands, shell state, and terminal window placement are not saved. An `open` operation can leave earlier tabs open if Ptyxis fails on a later tab.

Remove the command with `./uninstall.sh --module termlay` or this module's `uninstall.sh`. Saved layouts are user data and remain on disk.

The scripts keep each class in its own PascalCase file. `scripts/layout/` owns layout data, storage, and path validation; `scripts/ptyxis/` owns tab discovery, process lookup, capture prompts, and opening tabs. The manifest installs their helpers beside `termlay` so the command works from any directory.

Run `python3 src/modules/system-utilities/termlay/tests/TermlayTest.py` for focused CLI and storage tests. The test uses a fake Ptyxis executable and a temporary home; it does not open terminal windows.
