# Installation module

`catalog/` validates the catalog and module manifests. `catalog/loader.py` reads the root map, `manifest.py` assembles definitions, `source.py` validates paths, and `commands.py`, `assets.py`, and `lifecycle.py` validate their respective manifest fields. `catalog/__init__.py` exports the loaded map and component helpers. `selection/available.py` handles setup choices; `selection/installed.py` routes update and removal choices; `selection/inventory.py` loads local and remote ownership. `main.py` is the shared transaction CLI. The implementation is grouped by concern and lifecycle:

| Directory | Responsibility |
| --- | --- |
| `catalog/` | Root map, manifest validation, path safety, and component ownership. |
| `core/` | Registry paths, locking, migration, inventory, atomic files, rollback, and user profile ownership. |
| `selection/` | Available and installed selections, inventory loading, and scope routing. |
| `setup/` | Root setup orchestration, generated command builds, and the shared install transaction. |
| `update/` | Root update orchestration and refresh of installed selections through the install transaction. |
| `uninstall/` | Root removal orchestration, ownership checks, hooks, deletion, and rollback. |
| `remote/` | SSH snippets/transport and local remote-deployment records. |
| `portable/` | One canonical helper, bundled into temporary SSH archives. |
| `main.py` | Stable root entry for shared install, update, and removal transactions. |
| `module_entry.sh` | One direct setup/uninstall router used by module entry links. |

Keep the registry lock around each complete read/check/write operation. Shared helpers belong in `core/` only when two lifecycles need them. Prefer focused functions; add a class when it owns persistent state or a meaningful interface, not merely to replace a function file. Each module manifest includes its direct workflow commands and any non-executable support files they need.

Root `main.sh` asks for setup, update, or uninstall and dispatches to the canonical `scripts/` action script. Those scripts call `installer/main.py` with `setup`, `select-update`, and `select-uninstall`, which routes to the matching lifecycle orchestrator. The orchestrators send selected batches back to `main.py` with the internal `install`, `update`, or `uninstall` action. Each module's direct `setup.sh` and `uninstall.sh` is a link to `installer/module_entry.sh`, which routes through the same root scripts. Update selects registered modules across scopes and refreshes only installed commands and components; it does not run post-install prompts or pre-remove hooks. `--module NAME` can be repeated; `--all` selects all available or installed modules. `--list` shows available or registered modules.

Modules with manifest `components` also accept repeatable `--component MODULE:NAME`. Each component owns a disjoint set of commands. Selecting the full module includes every component; selecting a component adds it to any previously installed components. Removing a component keeps its siblings. Older full-module registry records remain compatible. SSH bundles use local component names internally.

Interactive selection shows categories, then modules in each chosen category, then a sub-module menu for a componentized module. Setup filters that submenu using the selected scope's registry so it offers only components still available to install. Uninstall reads both registries and offers only installed components, showing user or system scope. It checks recorded files on disk for missing or modified copies and shows warnings; removal still uses registry ownership and hash checks. System registry reads and removals use sudo when needed. Explicit `--module NAME` and `--all` still select full modules.

The root [installation catalog](../configuration/install.json) lists module manifests and shared destinations. Each module's `module.json` owns its commands, display name, category, subcategory, build step, examples, and removal hook. The [catalog guide](../configuration/README.md) documents the fields. Module IDs remain stable for CLI and registry compatibility.

The root selector submits same-scope selections as one batch. Mixed user and system selections require `--system` or separate setup commands. Installation checks every selected file before copying, then restores installed files, the profile, and the registry if the batch fails. Reinstall removes obsolete owned commands and cron files only if their hashes still match the registry.

User installation copies commands to `~/.local/bin` and writes a mode-0600 JSON registry at `~/.local/state/shell-scripts/registry.json`. System installation with `--system` copies to `/usr/local/bin` and uses `/var/lib/shell-scripts/registry.json`. The registry stores source and installed paths, hashes, documentation, configuration examples, cron templates, runtime policy paths, and schedules.

System installation also places inactive backup and network cron templates in `/etc/cron.d` and records their hashes. Uninstall checks installed commands and managed cron files against registered hashes. A locally changed file is preserved unless `--force` is supplied. Module-owned removal hooks clean up Privacy schedules, Ubuntu policy, and Canary services. Privacy policy files remain unless `--purge-config` is supplied. A user PATH line added by setup is removed when the last user module is removed.

The `system-update` module owns the manual `update-system` command. Shared registries that still store it as `system:update` are translated when loaded, so the recorded command stays removable. The `system` module retains the AMD gaming and H848 audio components.

The `ubuntu-updates` module is system-only. Root setup passes `--system` for it; installing its command does not apply an APT policy. Its system uninstall invokes the installed command's verified `restore --yes` before removing it. This removes only an unchanged policy owned by the module and restores recorded timer enablement and activity. It preserves packages, updates, and locally edited or unmanaged policy files.

The `canary` module is also system-only. Its C binary is compiled before the install transaction. Installing it does not configure or start a service. Its system uninstall invokes the verified installed `canary-remove-all --yes`, which removes owned systemd units and config files after hash checks and leaves watched targets and JSONL logs intact.

The `vps-gateway` module is system-only. Installation registers its host command and self-contained site generator without changing host packages or services. Interactive setup offers an optional first-run site wizard. Its explicit `configure` installs distribution NGINX and Certbot packages and enables NGINX. Uninstall removes only the commands; distribution packages, service state, NGINX and Certbot data, and application site files remain for their owners.

The only portable helper source lives in `installer/portable/`: `portable_module.py` loads a selected module manifest, and `portable_support/` owns locking and state, file safety, hooks, planning, installation, and removal. Module source directories do not contain helper copies. For SSH setup, update, and uninstall, `remote/deploy.py` adds the canonical helper to a temporary archive beside the selected module, then runs it on the target. Remote installations use separate state under `shell-scripts/portable/`; the helper provides per-module rollback. Local setup and removal use the shared installer, registry, and cross-module transactions.

`--ssh TARGET` uses `remote/deploy.py` to send each selected module and the canonical portable helper as a temporary archive, then run the requested action on the target. `remote/state.py` records successful deployments under `remote_deployments` in the local user registry, separate from locally owned commands. The standalone target programs live in `remote/scripts/bootstrap.py` (extract and run an action) and `remote/scripts/scan.py` (inspect portable state); `remote/scripts/__init__.py` loads their source for SSH execution. Remote selection and listing scan the target's portable state and report differences from the local record. Remote uninstall uses the target's hash checks. Remote installs are per module, and system scope requires noninteractive sudo on the target. The focused test uses a mock SSH command and two temporary home directories.

The installation tests use temporary home and system prefixes: `bash installer/tests/lifecycle/setup_test.sh`, `python3 installer/tests/ui/orchestrator_ui_test.py`, `python3 installer/tests/lifecycle/transaction_test.py`, and `python3 installer/tests/portable/portable_modules_test.py`.
Run `python3 installer/tests/lifecycle/component_test.py` for component lifecycle checks.
Run `python3 installer/tests/lifecycle/registry_routing_test.py` for direct and root wrapper routing across both scopes.
Run `python3 installer/tests/remote/remote_deploy_test.py` for the SSH prototype and deployment record lifecycle.

Registry mutations hold one scope lock across fresh reads, ownership checks, file changes, rollback, and publication. Shared installers, updates, portable installers, and local SSH deployment records use the same scope lock. Update records the source hash for each installed command; `./main.sh update --list` reports source changes separately from installed-file integrity issues. Lock files remain in place after uninstall. Profile cleanup refuses symbolic links before removing commands and publishes the edited profile atomically. Run `python3 installer/tests/lifecycle/concurrency_test.py` for overlapping-operation and profile safety checks.

Recovery catches Python exceptions and Ctrl+C during installation and restores
managed files and registry state. Uninstall restores the current module's command
files, cron templates, registry, and final user-profile cleanup if deletion or
state publication fails. Earlier successful module removals remain committed.
Removal-hook changes to services, schedules, or policies are not rolled back;
the restored commands allow removal to be retried. These are in-process recovery
guarantees, not recovery after SIGKILL, power loss, or a second failure during
rollback. Standalone installers provide equivalent command/state recovery.
Run `python3 installer/tests/lifecycle/recovery_test.py` for injected interruption,
file deletion, and registry publication failures, or `python3 installer/verify.py`
for the complete suite.

Explicit updates prefer the user installation and consult system state only when
needed to find a selection. `--system` restricts the scope; `--all` updates both
scopes by default, with a separate transaction for each scope. A full module
update retains its installed component selection. Local source-hash hints cover
command sources, not every build dependency; an update always rebuilds selected
commands. Older registry entries acquire source hashes on their next refresh.
Run `python3 installer/tests/lifecycle/update_test.py` for update ownership and
scope checks, and `remote_deploy_test.py` for portable update state checks.
