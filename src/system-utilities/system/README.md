# System utilities

Install from the repository root with `src/system-utilities/system/setup.sh` or `./main.sh setup --module system`. The direct entry points require the repository installer. Add `--system` and use sudo for system-wide command availability. Run the installed device tools as a normal desktop user; they invoke `sudo` only where needed.

Install or remove the two utilities independently:

```bash
./main.sh setup --component system:amd-gaming
./main.sh setup --component system:h848-audio

# Direct entry points use local component names:
src/system-utilities/system/setup.sh --component h848-audio
src/system-utilities/system/uninstall.sh --component h848-audio
```

`--module system` and direct entry points without `--component` still select both. Removing `h848-audio` removes its command files; run `uninstall-h848-audio-fix` first if you also want an applied fix restored.

Interactive root setup and uninstall first ask for `system`, then show a sub-module menu. Setup reads the selected scope's registry and lists only sub-modules not yet installed. Uninstall lists only installed sub-modules. Enter multiple numbers or `all` at that second menu to manage several at once.

## AMD gaming setup

`install-amd-gaming` installs Ubuntu packages for an AMD Radeon gaming setup, including Vulkan, Steam, Mesa, GameMode, MangoHud, and Proton tools. Review it before use on another distribution or hardware configuration. Reboot after installation.

## H848 audio fix

`uninstall-h848-audio-fix` is the direct removal command; the original `install-h848-audio-fix --uninstall` form also works.

`install-h848-audio-fix` configures PipeWire/WirePlumber for the Redragon H848 USB audio device on Ubuntu or compatible APT-based systems. Use `install-h848-audio-fix --uninstall` to restore original configuration files and remove files created by the installer. It stores timestamped backups under `${HOME}/.local/state/h848-audio-fix/backups/` and original files under `original/`. Run `bash src/system-utilities/system/tests/h848_uninstall_test.sh` for the mocked uninstall check.

The installer reads its WirePlumber 0.4/0.5 and systemd templates from files beside the command. The module manifest installs those three non-executable companion files with the H848 component, including in temporary SSH deployments.
