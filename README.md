# Linux-Utilities

Independent Linux utilities organized by concern under `src/modules/`. The root setup asks for category, module, then sub-module when needed, and installs selected modules as one batch. Each module also has its own setup and uninstall scripts. The stable module IDs are used in commands and registries; display names and categories help people find the right tool.

Setup and uninstall require Python 3.9 or newer. Runtime requirements are listed in each module README.

## Install and remove

```bash
./setup.sh                         # interactive user install
./setup.sh --module backup --module privacy
./setup.sh --ssh my-server --module network
./setup.sh --ssh my-server --component system:amd-gaming
./setup.sh --module system-update
./setup.sh --module termlay
./setup.sh --module log-scout
./setup.sh --component system:h848-audio
sudo ./setup.sh --system --all
./setup.sh --list
src/modules/data-privacy/privacy/setup.sh              # direct setup of one module
src/modules/data-privacy/privacy/uninstall.sh          # direct removal of one module
./uninstall.sh                     # interactive module selection
./uninstall.sh --module privacy
./uninstall.sh --module ubuntu-updates  # finds its system registry entry
./uninstall.sh --ssh my-server --list
./uninstall.sh --ssh my-server --module network
./uninstall.sh --module system-update
```

You can run any `src/modules/<category>/<module>/setup.sh` or `uninstall.sh` directly. Within this checkout, they use the shared registry and transaction manager. A copied module directory uses its own `module.json` and portable installer with a separate registry under `shell-scripts/portable/`. Its installed commands work without the repository; use the full path to `~/.local/bin` if that directory is not on PATH. Privacy's repository setup offers to configure retention when run in a terminal; `--no-configure` skips that prompt. Scripted root installs stay noninteractive.

The root selector installs all selected modules in one transaction for one scope. The `ubuntu-updates`, `canary`, and `vps-gateway` modules require system scope; combine them with other modules using `--system`, or install them separately. An install failure restores the previously installed files and registry. Reinstall removes obsolete managed commands and cron templates when their installed copies are unchanged; locally edited copies block the reinstall.

For a small SSH deployment, pass `--ssh TARGET` with the same module or component selection options. The wrapper sends each selected module directory to the target and runs that module's portable setup there. Successful deployments are recorded under `remote_deployments` in the local user registry; `./uninstall.sh --ssh TARGET --list` also scans the target's portable registry and flags differences. `--module` or `--component` removes a selection using the target's own hash checks. A failed remote operation leaves the local deployment record in place. SSH deployment needs Git and SSH locally and Python 3.9 or newer on the target. Remote system installs require noninteractive sudo access on the target; modules are deployed one at a time, so a multi-module SSH selection is not one remote transaction.

The `system` module offers independently managed `system:amd-gaming` and `system:h848-audio` components. Manual package updates are the separate `system-update` module under Server services; legacy `system:update` registry entries migrate when read. In the interactive menu, select System utilities, then `system`, then one or more sub-modules. Setup shows sub-modules not yet installed; uninstall shows only those recorded as installed. Use repeatable `--component MODULE:NAME` options for scripted selection. Explicit `--module system` selects both. Adding or removing one component leaves installed siblings registered. `--list` reflects the available setup or uninstall selections. Installing these commands does not run the utilities.

The default installation copies selected commands to `~/.local/bin` and records them in `~/.local/state/shell-scripts/registry.json`. The existing `shell-scripts` state paths and markers stay in place so installed modules remain manageable after the project rename. If needed, setup adds `~/.local/bin` to `~/.profile`; open a new shell or source that file before calling commands by name. The registry records command paths and hashes, source files, configuration examples, cron templates, and runtime policy paths. Root uninstall reads both user and system registries, labels their scopes, and checks recorded command files against their hashes. It may ask for sudo to read the private system registry or remove a system module. Uninstall removes only registered commands, refuses locally modified files unless `--force` is supplied, and removes managed privacy schedules. It preserves privacy policy files unless `--purge-config` is supplied.

For commands available to every account, use `sudo ./setup.sh --system --all`. That installs to `/usr/local/bin`, places inactive backup and network cron templates under `/etc/cron.d`, and records `/var/lib/shell-scripts/registry.json`; remove with `./uninstall.sh --system`. `--list` shows available modules for setup or registered modules for uninstall. You can repeat `--module NAME` or use `--all`. When the same full module exists in both scopes, explicit removal defaults to the user copy; add `--system` for the system copy. An explicit component selection finds the scope where that component is installed.

The root [installation catalog](configuration/install.json) lists module manifests and shared install destinations. Each module manifest owns its display name, category, subcategory, commands, examples, build step, and removal hook. See the [catalog guide](configuration/README.md). Generated registries stay outside Git.

Installed commands:

| Category / subcategory | Module (stable ID) | Commands |
| --- | --- | --- |
| Data and privacy / Backups | Home backup and remote copy (`backup`) | `backup-home`, `backup-home-cron`, `backup-home-prune`, `fetch-remote-backup` |
| Data and privacy / Retention | History and log cleanup (`privacy`) | `privacy-configure`, `privacy-status`, `privacy-run`, `privacy-scheduled`, `privacy-uninstall-schedule` |
| Monitoring / Log analysis | Linux log triage prototype (`log-scout`) | `log-scout` |
| Monitoring / Network capture | Packet capture (`network`) | `capture-traffic` |
| Monitoring / File events | Canary file monitoring (`canary`) | `fs-tracker`, `canary-configure`, `canary-status`, `canary-start`, `canary-stop`, `canary-remove`, `canary-remove-all` (system install) |
| System utilities / Workstation setup | System utilities (`system`) | `install-amd-gaming`, `install-h848-audio-fix`, `uninstall-h848-audio-fix` |
| System utilities / Terminal workflow | Terminal layouts (`termlay`) | `termlay` |
| Server services / Package maintenance | Manual APT updates (`system-update`) | `update-system` |
| Server services / Package maintenance | Ubuntu automatic updates (`ubuntu-updates`) | `ubuntu-updates-configure`, `ubuntu-updates-status`, `ubuntu-updates-logs`, `ubuntu-updates-dry-run`, `ubuntu-updates-run`, `ubuntu-updates-restore` (system install) |
| Server services / Web gateway | NGINX and Certbot setup (`vps-gateway`) | `vps-gateway-configure`, `vps-gateway-status`, `vps-gateway-init`, `vps-gateway-add`, `vps-gateway-site-list`, `vps-gateway-site-render`, `vps-gateway-site-import` (system install) |

The previous multi-command entry points (`privacy-cleanup`, `ubuntu-updates`, `canary-control`, `vps-gateway`, and `vps-gateway-site`) remain installed for existing scripts. Each named workflow above can now be called directly. Some commands still require privileges for their own job. Privacy defaults to the current user's files without sudo; `--system` is optional and requires sudo. Read the module README before using a host-changing command.

`ubuntu-updates` is system-scope because its explicit `configure` command manages host APT policy and timers. Selecting it in the root setup UI installs the command system-wide but does not apply a policy. See the [module guide](src/modules/server-services/ubuntu-updates/README.md) for commands, rollback, and the legacy-policy check.

`canary` is system-scope because its named services use systemd and fanotify privileges. Setup compiles and installs the sensor but does not create or start a service. See the [canary guide](src/modules/monitoring/canary/README.md) for configuration and safe removal.

`vps-gateway` is system-scope. Run `sudo vps-gateway-init --empty` to install the core and catch-all without a first project site; the interactive initializer also offers this choice. Project installers can then import their own routes with `sudo vps-gateway-site-import --host NAME --file PATH` or stream them through standard input with `--file -`. Run `sudo vps-gateway-add` for interactive site creation. `sudo vps-gateway-configure` remains package-only. See the [VPS gateway guide](src/modules/server-services/vps-gateway/README.md).

`termlay` saves named directories under the XDG configuration directory and opens them as Ptyxis tabs. Run `termlay save-current work` in a Ptyxis window to discover its tabs, or `termlay save work ~/dev/frontend ~/dev/backend` to enter directories manually; then run `termlay open work`. Interactive opening reuses the origin tab for the first directory, avoiding an extra tab; `--new-tabs` opens every entry in a new tab. See the [terminal layouts guide](src/modules/system-utilities/termlay/README.md) for storage, commands, and limitations.

`log-scout` scans recent journal entries or selected text logs, summarizes warning/error
categories, and lets you drill into repeated-message groups and representative examples.
Run `log-scout` for scan-and-browse, `log-scout scan --file /path/to/app.log` for a text log,
and `log-scout summary`, `log-scout details network`, or `log-scout history` to reopen
private cached scans. It is a bounded, read-only prototype; coverage limits and source
failures are shown in each summary. See the [log triage guide](src/modules/monitoring/log-scout/README.md).

## Layout

```text
setup.sh, uninstall.sh, README.md
configuration/   shared installation catalog and its documentation
src/
  installation/   registry-based setup/uninstall logic and tests
  modules/
    data-privacy/    backup/, privacy/
    monitoring/      network/, canary/, log-scout/
    system-utilities/ system/ and termlay/
    server-services/ system-update/, ubuntu-updates/, vps-gateway/
.agents/          compact agent project map, qualities, debugging, cache
```

Configuration examples use `.env.example` or `.cfg.example`. Local policy files and generated data are kept outside the repository. See each module README for settings and retention or rollback behavior.

For maintenance, start with the [project map](.agents/PROJECT_CACHE.md), follow the [code qualities](.agents/QUALITIES.md), and use the [spring cleanup guide](.agents/REPOSITORY_SPRING_CLEANING.md) when moving modules or files. Keep Python classes in matching `PascalCase.py` files and update test discovery commands when renaming tests.

## Verify

Run the complete isolated suite from the repository root:

```bash
python3 scripts/verify.py
```

The runner checks Python 3.9 syntax, Bash syntax, ShellCheck, all module suites,
installer recovery, concurrency, routing, SSH transport mocks, and standalone
portability. It continues after failed checks and returns a nonzero exit status
if any check fails. Tests use temporary homes/install roots and mocked host
operations; they do not run live backups, capture, cleanup, or system services.

Use a Debian/Ubuntu test environment with Python 3.9+, Bash, ShellCheck, a C
compiler (`build-essential`), Git, GNU coreutils, tar, bzip2, util-linux (`flock`),
and APT (`apt-config`). No Python packages are required for this suite. Individual
module READMEs retain focused test commands. The GitHub Actions workflow runs the
same runner on Ubuntu with Python 3.9 and 3.14 for pushes and pull requests.
