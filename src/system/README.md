# System utilities

Install from the repository root with `src/system/setup.sh` or `./setup.sh --module system`. A copied module directory has its own `./setup.sh` and `./uninstall.sh`. Add `--system` and use sudo for system-wide command availability. Run the installed device tools as a normal desktop user; they invoke `sudo` only where needed.

## Package updates

Run `update-system` to refresh APT package lists and install available upgrades with `apt upgrade -y`. The command uses `sudo` when run as a normal user and runs APT directly as root. It stops if `apt update` fails, so no upgrade is attempted with stale package lists. It accepts no arguments and does not perform a distribution upgrade or package removal. Run `bash src/system/tests/update_system_test.sh` for the mocked command and installation check.

## AMD gaming setup

`install-amd-gaming` installs Ubuntu packages for an AMD Radeon gaming setup, including Vulkan, Steam, Mesa, GameMode, MangoHud, and Proton tools. Review it before use on another distribution or hardware configuration. Reboot after installation.

## H848 audio fix

`uninstall-h848-audio-fix` is the direct removal command; the original `install-h848-audio-fix --uninstall` form also works.

`install-h848-audio-fix` configures PipeWire/WirePlumber for the Redragon H848 USB audio device on Ubuntu or compatible APT-based systems. Use `install-h848-audio-fix --uninstall` to restore original configuration files and remove files created by the installer. It stores timestamped backups under `${HOME}/.local/state/h848-audio-fix/backups/` and original files under `original/`. Run `bash src/system/tests/h848_uninstall_test.sh` for the mocked uninstall check.
