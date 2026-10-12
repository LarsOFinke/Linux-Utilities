# System utilities

Setup and update need `cc` and install one ELF executable for the module. The H848 templates and Bash helper are embedded; an update of the H848 component removes older registry-owned companion files. Python 3.9+ is needed to launch the commands. The audio fix still creates its documented user configuration and service files when run.

Install from the repository root with `src/system-utilities/system/setup.sh` or `./main.sh setup --module system`. The direct entry points require the repository installer. Add `--system` and use sudo for system-wide command availability. Run the installed device tools as a normal desktop user; they invoke `sudo` only where needed.

Install or remove the two utilities independently:

```bash
./main.sh setup --component system:amd-gaming
./main.sh setup --component system:h848-audio

# Direct entry points use local component names:
src/system-utilities/system/setup.sh --component h848-audio
src/system-utilities/system/uninstall.sh --component h848-audio
```

`--module system` and direct entry points without `--component` still select both. `system-utils` checks the installed component registry before running a subcommand. Removing the last component removes the binary; run `system-utils h848-audio uninstall` first if you also want an applied fix restored.

Interactive root setup and uninstall first ask for `system`, then show a sub-module menu. Setup reads the selected scope's registry and lists only sub-modules not yet installed. Uninstall lists only installed sub-modules. Enter multiple numbers or `all` at that second menu to manage several at once.

## AMD gaming setup

`system-utils amd-gaming` installs Ubuntu packages for an AMD Radeon gaming setup, including Vulkan, Steam, Mesa, GameMode, MangoHud, and Proton tools. Review it before use on another distribution or hardware configuration. Reboot after installation.

## H848 audio fix

`system-utils h848-audio uninstall` restores the applied audio configuration before you remove the component.

`system-utils h848-audio install` configures PipeWire/WirePlumber for the Redragon H848 USB audio device on Ubuntu or compatible APT-based systems. Use `system-utils h848-audio uninstall` to restore original configuration files and remove files created by the installer. It stores timestamped backups under `${HOME}/.local/state/h848-audio-fix/backups/` and original files under `original/`. Run `bash src/system-utilities/system/tests/h848_uninstall_test.sh` for the mocked uninstall check.

The `system-utils` executable unpacks its WirePlumber 0.4/0.5 and systemd templates into private temporary storage while it runs. It copies the selected templates into their user configuration locations when the fix is applied.
