# Manual APT updates

Install `update-system` independently with `./main.sh setup --module system-update` from the repository root or `src/server-services/system-update/setup.sh` directly. The default command install is in the current user's `~/.local/bin`; use `--system` for a system-wide command. The direct entry point requires the repository installer; SSH deployment bundles the canonical portable helper temporarily.

Run `update-system` to refresh APT package lists and install available upgrades with `apt upgrade -y`. It uses `sudo` when run by a normal user. It stops when `apt update` fails and accepts no arguments. It does not perform a distribution upgrade or package removal.

Remove the command with `./main.sh uninstall --module system-update` or the module's direct `uninstall.sh`. Existing shared-registry `system:update` installations are migrated to the `system-update` registry entry when the current wrapper reads the registry. See the root README for registry and scope behavior.

Run `bash src/server-services/system-update/tests/update_system_test.sh` for the mocked behavior and lifecycle test.
