# Linux-Utilities

Independent Linux utilities organized by module under `src/`. The root setup is an interactive module selector that installs selected modules as one batch. Each module also has its own setup and uninstall scripts. The stable module IDs are used in commands and registries; display names and categories help people find the right tool.

Setup and uninstall require Python 3.9 or newer. Runtime requirements are listed in each module README.

## Install and remove

```bash
./setup.sh                         # interactive user install
./setup.sh --module backup --module privacy
./setup.sh --component system:update
./setup.sh --component system:h848-audio
sudo ./setup.sh --system --all
./setup.sh --list
src/privacy/setup.sh              # direct setup of one module
src/privacy/uninstall.sh          # direct removal of one module
./uninstall.sh                     # interactive module selection
./uninstall.sh --module privacy
./uninstall.sh --module ubuntu-updates  # finds its system registry entry
./uninstall.sh --component system:update
```

You can run any `src/<module>/setup.sh` or `uninstall.sh` directly. Within this checkout, they use the shared registry and transaction manager. A copied module directory uses its own `module.json` and portable installer with a separate registry under `shell-scripts/portable/`. Its installed commands work without the repository; use the full path to `~/.local/bin` if that directory is not on PATH. Privacy's repository setup offers to configure retention when run in a terminal; `--no-configure` skips that prompt. Scripted root installs stay noninteractive.

The root selector installs all selected modules in one transaction for one scope. The `ubuntu-updates`, `canary`, and `vps-gateway` modules require system scope; combine them with other modules using `--system`, or install them separately. An install failure restores the previously installed files and registry. Reinstall removes obsolete managed commands and cron templates when their installed copies are unchanged; locally edited copies block the reinstall.

The `system` module offers independently managed `system:update`, `system:amd-gaming`, and `system:h848-audio` components. In the interactive menu, select `system` first, then select one or more sub-modules. Setup shows sub-modules not yet installed; uninstall shows only those recorded as installed. Use repeatable `--component MODULE:NAME` options for scripted selection. Explicit `--module system` still selects all three. Adding or removing one component leaves installed siblings registered. `--list` reflects the available setup or uninstall selections. Installing these commands does not run the utilities.

The default installation copies selected commands to `~/.local/bin` and records them in `~/.local/state/shell-scripts/registry.json`. The existing `shell-scripts` state paths and markers stay in place so installed modules remain manageable after the project rename. If needed, setup adds `~/.local/bin` to `~/.profile`; open a new shell or source that file before calling commands by name. The registry records command paths and hashes, source files, configuration examples, cron templates, and runtime policy paths. Root uninstall reads both user and system registries, labels their scopes, and checks recorded command files against their hashes. It may ask for sudo to read the private system registry or remove a system module. Uninstall removes only registered commands, refuses locally modified files unless `--force` is supplied, and removes managed privacy schedules. It preserves privacy policy files unless `--purge-config` is supplied.

For commands available to every account, use `sudo ./setup.sh --system --all`. That installs to `/usr/local/bin`, places inactive backup and network cron templates under `/etc/cron.d`, and records `/var/lib/shell-scripts/registry.json`; remove with `./uninstall.sh --system`. `--list` shows available modules for setup or registered modules for uninstall. You can repeat `--module NAME` or use `--all`. When the same full module exists in both scopes, explicit removal defaults to the user copy; add `--system` for the system copy. An explicit component selection finds the scope where that component is installed.

The root [installation catalog](configuration/install.json) lists module manifests and shared install destinations. Each `src/<module>/module.json` owns its display name, category, commands, examples, build step, and removal hook. See the [catalog guide](configuration/README.md). Generated registries stay outside Git.

Installed commands:

| Category | Module (stable ID) | Commands |
| --- | --- | --- |
| Data and privacy | Home backup and remote copy (`backup`) | `backup-home`, `backup-home-cron`, `backup-home-prune`, `fetch-remote-backup` |
| Data and privacy | History and log cleanup (`privacy`) | `privacy-configure`, `privacy-status`, `privacy-run`, `privacy-scheduled`, `privacy-uninstall-schedule` |
| Monitoring | Packet capture (`network`) | `capture-traffic` |
| Monitoring | Canary file monitoring (`canary`) | `fs-tracker`, `canary-configure`, `canary-status`, `canary-start`, `canary-stop`, `canary-remove`, `canary-remove-all` (system install) |
| System utilities | System utilities (`system`) | `update-system`, `install-amd-gaming`, `install-h848-audio-fix`, `uninstall-h848-audio-fix` |
| Server services | Ubuntu automatic updates (`ubuntu-updates`) | `ubuntu-updates-configure`, `ubuntu-updates-status`, `ubuntu-updates-logs`, `ubuntu-updates-dry-run`, `ubuntu-updates-run`, `ubuntu-updates-restore` (system install) |
| Server services | NGINX and Certbot setup (`vps-gateway`) | `vps-gateway-configure`, `vps-gateway-status`, `vps-gateway-init`, `vps-gateway-add`, `vps-gateway-site-list`, `vps-gateway-site-render` (system install) |

The previous multi-command entry points (`privacy-cleanup`, `ubuntu-updates`, `canary-control`, `vps-gateway`, and `vps-gateway-site`) remain installed for existing scripts. Each named workflow above can now be called directly. Some commands still require privileges for their own job. Privacy defaults to the current user's files without sudo; `--system` is optional and requires sudo. Read the module README before using a host-changing command.

`ubuntu-updates` is system-scope because its explicit `configure` command manages host APT policy and timers. Selecting it in the root setup UI installs the command system-wide but does not apply a policy. See the [module guide](src/ubuntu-updates/README.md) for commands, rollback, and the legacy-policy check.

`canary` is system-scope because its named services use systemd and fanotify privileges. Setup compiles and installs the sensor but does not create or start a service. See the [canary guide](src/canary/README.md) for configuration and safe removal.

`vps-gateway` is system-scope. Interactive setup offers a first-run wizard to choose a blueprint, fill in its host and port or document root, and activate the core, catch-all, and first site. Run `sudo vps-gateway-add` to add later hostnames through the same kind of prompts. `sudo vps-gateway-configure` remains package-only. See the [VPS gateway guide](src/vps-gateway/README.md).

## Layout

```text
setup.sh, uninstall.sh, README.md
configuration/   shared installation catalog and its documentation
src/
  backup/         scripts, configuration, cronjobs, tests
  network/        scripts, configuration, cronjobs, tests
  system/         scripts, tests
  privacy/        scripts, configuration, cronjobs, tests
  ubuntu-updates/ scripts, tests
  canary/         C sensor, control command, tools, docs, tests
  vps-gateway/    NGINX and Certbot host bootstrap, core and site blueprints, tests
  installation/   registry-based setup/uninstall logic and tests
.agents/          compact agent project map, qualities, debugging, cache
```

Configuration examples use `.env.example` or `.cfg.example`. Local policy files and generated data are kept outside the repository. See each module README for settings and retention or rollback behavior.

## Verify

```bash
find src -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
shellcheck setup.sh uninstall.sh src/*/setup.sh src/*/uninstall.sh src/installation/setup_module.sh src/*/scripts/*.sh src/*/tests/*.sh
bash src/backup/tests/backup_home_test.sh
bash src/network/tests/capture_traffic_test.sh
bash src/system/tests/h848_uninstall_test.sh
bash src/system/tests/update_system_test.sh
bash src/privacy/tests/privacy_cleanup_test.sh
bash src/ubuntu-updates/tests/ubuntu_updates_test.sh
bash src/canary/tests/integration_test.sh
bash src/canary/tests/c_unit_test.sh
bash src/vps-gateway/tests/vps_gateway_test.sh
PYTHONPATH=src/canary python3 -m unittest discover -s src/canary/tests -p 'test_*.py'
bash src/installation/tests/setup_test.sh
python3 src/installation/tests/orchestrator_ui_test.py
python3 src/installation/tests/transaction_test.py
python3 src/installation/tests/portable_modules_test.py
python3 src/installation/tests/component_test.py
python3 src/installation/tests/registry_routing_test.py
```
