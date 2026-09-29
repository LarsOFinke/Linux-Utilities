# Installation module

`catalog.py` validates module manifests and selections. `manage.py` owns registry transactions and installation. Each module manifest includes its direct workflow commands and any non-executable support files they need.

`setup.sh` at the repository root calls `orchestrate.py`, an interactive selector that sends the selection to the registry backend in `manage.py` as one batch. Each `src/modules/<concern>/<module>/setup.sh` can also be used directly through `setup_module.sh`. Root `uninstall.sh` calls `uninstall_orchestrate.py`, which reads both scope registries and sends selected removals to `manage.py`. `--module NAME` can be repeated; `--all` selects all available modules. `--list` shows available or registered modules.

Modules with manifest `components` also accept repeatable `--component MODULE:NAME`. Each component owns a disjoint set of commands. Selecting the full module includes every component; selecting a component adds it to any previously installed components. Removing a component keeps its siblings. Older full-module registry records remain compatible. A copied module accepts `--component NAME`.

Interactive selection shows categories, then modules in each chosen category, then a sub-module menu for a componentized module. Setup filters that submenu using the selected scope's registry so it offers only components still available to install. Uninstall reads both registries and offers only installed components, showing user or system scope. It checks recorded files on disk for missing or modified copies and shows warnings; removal still uses registry ownership and hash checks. System registry reads and removals use sudo when needed. Explicit `--module NAME` and `--all` still select full modules.

The root [installation catalog](../../configuration/install.json) lists module manifests and shared destinations. Each module's `module.json` owns its commands, display name, category, subcategory, build step, examples, and removal hook. The [catalog guide](../../configuration/README.md) documents the fields. Module IDs remain stable for CLI and registry compatibility.

The root selector submits same-scope selections as one batch. Mixed user and system selections require `--system` or separate setup commands. Installation checks every selected file before copying, then restores installed files, the profile, and the registry if the batch fails. Reinstall removes obsolete owned commands and cron files only if their hashes still match the registry.

User installation copies commands to `~/.local/bin` and writes a mode-0600 JSON registry at `~/.local/state/shell-scripts/registry.json`. System installation with `--system` copies to `/usr/local/bin` and uses `/var/lib/shell-scripts/registry.json`. The registry stores source and installed paths, hashes, documentation, configuration examples, cron templates, runtime policy paths, and schedules.

System installation also places inactive backup and network cron templates in `/etc/cron.d` and records their hashes. Uninstall checks installed commands and managed cron files against registered hashes. A locally changed file is preserved unless `--force` is supplied. Module-owned removal hooks clean up Privacy schedules, Ubuntu policy, and Canary services. Privacy policy files remain unless `--purge-config` is supplied. A user PATH line added by setup is removed when the last user module is removed.

The `system-update` module owns the manual `update-system` command. Shared registries that still store it as `system:update` are translated when loaded, so the recorded command stays removable. The `system` module retains the AMD gaming and H848 audio components.

The `ubuntu-updates` module is system-only. Root setup passes `--system` for it; installing its command does not apply an APT policy. Its system uninstall invokes the installed command's verified `restore --yes` before removing it. This removes only an unchanged policy owned by the module and restores recorded timer enablement and activity. It preserves packages, updates, and locally edited or unmanaged policy files.

The `canary` module is also system-only. Its C binary is compiled before the install transaction. Installing it does not configure or start a service. Its system uninstall invokes the verified installed `canary-remove-all --yes`, which removes owned systemd units and config files after hash checks and leaves watched targets and JSONL logs intact.

The `vps-gateway` module is system-only. Installation registers its host command and self-contained site generator without changing host packages or services. Interactive setup offers an optional first-run site wizard. Its explicit `configure` installs distribution NGINX and Certbot packages and enables NGINX. Uninstall removes only the commands; distribution packages, service state, NGINX and Certbot data, and application site files remain for their owners.

When a module directory is copied elsewhere, its `setup.sh` and `uninstall.sh` use the bundled `portable_module.py` and a separate state file under `shell-scripts/portable/`. The canonical helper is `src/installation/portable_module.py`; run `python3 src/installation/sync_portable_helpers.py` after editing it. The portability test checks that copies stay byte-for-byte in sync. This local fallback has per-module rollback, while the root installer provides cross-module transactions and user PATH setup.

`--ssh TARGET` uses `remote_deploy.py` to send each selected module as a temporary archive and run its portable setup or uninstall on the target. The local user registry stores successful remote deployments under `remote_deployments`, separate from locally owned commands. Remote selection and listing scan the target's portable state and report differences from the local record. Remote uninstall uses the target's hash checks. Remote installs are per module, and system scope requires noninteractive sudo on the target. The focused test uses a mock SSH command and two temporary home directories.

The installation tests use temporary home and system prefixes: `bash src/installation/tests/setup_test.sh`, `python3 src/installation/tests/orchestrator_ui_test.py`, `python3 src/installation/tests/transaction_test.py`, and `python3 src/installation/tests/portable_modules_test.py`.
Run `python3 src/installation/tests/component_test.py` for component lifecycle checks.
Run `python3 src/installation/tests/registry_routing_test.py` for direct and root wrapper routing across both scopes.
Run `python3 src/installation/tests/remote_deploy_test.py` for the SSH prototype and deployment record lifecycle.
