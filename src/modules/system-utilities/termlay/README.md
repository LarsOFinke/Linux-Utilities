# Terminal layouts (`termlay`)

Termlay saves the working directories of selected tabs in the focused Ptyxis window. `save`, `update`, and `delete` run as interactive wizards; `list` shows saved names without prompting:

```bash
termlay save
termlay update
termlay delete
termlay list
termlay ls
```

`save` lists the current window's tabs. Select numbers separated by commas, `all`, or `q` to cancel, then enter a name for the new layout. Tabs are stored in their visible order, even if numbers are entered in another order. Existing names cannot be overwritten by `save`.

`update` lists saved layouts, then current tabs. Select one layout and the tabs to use, review the resolved directories, and confirm replacement. `delete` lists saved layouts and requires confirmation before removing the selected ones. Layout and tab lists accept `q` to cancel; tab and delete lists also accept comma-separated numbers and `all`. A declined confirmation or cancelled tab selection leaves saved layouts unchanged.

`list` and its short alias `ls` print saved layout names alphabetically, one per line. They print nothing when there are no layouts and work without an interactive terminal or Ptyxis.

Tab discovery reads the focused Ptyxis window through AT-SPI. Standard shell titles provide a directory directly. For a uniquely matched local foreground process, Termlay reads its working directory, falling back to its owning shell. Matching follows executable symlinks and interpreter-launched scripts such as Codex. If a selected tab cannot be identified, Termlay asks for its directory. An empty answer cancels the operation. Paths are expanded, resolved to absolute directories, and checked before saving.

When several tabs run the same command, capture uses the workspace label in titles such as `Analyze this project | Linux-Utilities — node …/codex` to distinguish their directories. The label must match a directory belonging to a matching Ptyxis command. Ambiguous labels still require manual input. Shell titles with a running-command suffix retain their directory before the ` — ` separator.

Layouts are JSON files at `$XDG_CONFIG_HOME/termlay/layouts/<name>.json`, or `~/.config/termlay/layouts/<name>.json` when `XDG_CONFIG_HOME` is unset. `XDG_CONFIG_HOME` must be absolute. The layout directory is private (mode 0700), cannot be a symbolic link, and new files use mode 0600. The versioned file records a name and an ordered `tabs` array with each tab's `cwd`.

Install with `./setup.sh --module termlay` from the repository root, or run this module's `setup.sh` directly. The default install puts `termlay` and its Python helpers in `~/.local/bin`; `--system` is available for a shared command. Python 3.9 or newer is required at runtime. `save` and `update` also need Python GObject and AT-SPI bindings and a working desktop accessibility service. Installed commands work from any working directory.

Termlay captures only the focused Ptyxis window. It stores working directories, not commands, shell state, terminal window placement, or a way to reopen a layout. Remove the command with `./uninstall.sh --module termlay` or this module's `uninstall.sh`. Saved layouts are user data and remain on disk.

The scripts keep each class in its own PascalCase file. `scripts/layout/` owns layout data, storage, and path validation; `scripts/ptyxis/` owns tab discovery, process lookup, and capture prompts. The manifest installs their helpers beside `termlay`.

Run `python3 src/modules/system-utilities/termlay/tests/TermlayTest.py` for focused CLI and storage tests. Tests use temporary storage and mock tab discovery; they do not open terminal windows.
