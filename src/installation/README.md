# Installation module

`setup.sh` at the repository root calls `orchestrate.py`, an interactive selector that sends the selection to the registry backend in `manage.py` as one batch. Each `src/<module>/setup.sh` can also be used directly through `setup_module.sh`. Root `uninstall.sh` calls the registry backend directly. `--module NAME` can be repeated; `--all` selects all available modules. `--list` shows available or installed modules.

The root [installation catalog](../../configuration/install.json) lists module manifests and shared destinations. Each module's `module.json` owns its commands, display name, category, build step, examples, and removal hook. The [catalog guide](../../configuration/README.md) documents the fields. Module IDs remain stable for CLI and registry compatibility.

The root selector submits same-scope selections as one batch. Mixed user and system selections require `--system` or separate setup commands. Installation checks every selected file before copying, then restores installed files, the profile, and the registry if the batch fails. Reinstall removes obsolete owned commands and cron files only if their hashes still match the registry.

User installation copies commands to `~/.local/bin` and writes a mode-0600 JSON registry at `~/.local/state/shell-scripts/registry.json`. System installation with `--system` copies to `/usr/local/bin` and uses `/var/lib/shell-scripts/registry.json`. The registry stores source and installed paths, hashes, documentation, configuration examples, cron templates, runtime policy paths, and schedules.

System installation also places inactive backup and network cron templates in `/etc/cron.d` and records their hashes. Uninstall checks installed commands and managed cron files against registered hashes. A locally changed file is preserved unless `--force` is supplied. Module-owned removal hooks clean up Privacy schedules, Ubuntu policy, and Canary services. Privacy policy files remain unless `--purge-config` is supplied. A user PATH line added by setup is removed when the last user module is removed.

The `ubuntu-updates` module is system-only. Root setup passes `--system` for it; installing its command does not apply an APT policy. Its system uninstall invokes the installed command's verified `restore --yes` before removing it. This removes only an unchanged policy owned by the module and restores recorded timer enablement and activity. It preserves packages, updates, and locally edited or unmanaged policy files.

The `canary` module is also system-only. Its C binary is compiled before the install transaction. Installing it does not configure or start a service. Its system uninstall invokes the verified installed `canary-control remove-all --yes`, which removes owned systemd units and config files after hash checks and leaves watched targets and JSONL logs intact.

The `vps-gateway` module is system-only. Installation registers its command without changing host packages or services. Its explicit `configure` installs distribution NGINX and Certbot packages and enables NGINX. Uninstall removes only the command; distribution packages, service state, NGINX and Certbot data, and application site files remain for their owners.

When a module directory is copied elsewhere, its `setup.sh` and `uninstall.sh` use the bundled `portable_module.py` and a separate state file under `shell-scripts/portable/`. The canonical helper is `src/installation/portable_module.py`; run `python3 src/installation/sync_portable_helpers.py` after editing it. The portability test checks that copies stay byte-for-byte in sync. This local fallback has per-module rollback, while the root installer provides cross-module transactions and user PATH setup.

The installation tests use temporary home and system prefixes: `bash src/installation/tests/setup_test.sh`, `python3 src/installation/tests/orchestrator_ui_test.py`, `python3 src/installation/tests/transaction_test.py`, and `python3 src/installation/tests/portable_modules_test.py`.
