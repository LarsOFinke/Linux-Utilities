# Project cache

Read this compact map first, then the relevant module README. Root setup, update, and uninstall wrap independent modules.

| Concern | Module ID | Source | Focused test |
| --- | --- | --- | --- |
| Data and privacy | `backup` | `src/data-privacy/backup/` | `tests/backup_home_test.sh` |
| Data and privacy | `privacy` | `src/data-privacy/privacy/` | `tests/privacy_cleanup_test.sh` |
| Monitoring | `network` | `src/monitoring/network/` | `tests/capture_traffic_test.sh` |
| Monitoring | `log-scout` | `src/monitoring/log-scout/` | `tests/LogScoutTest.py` |
| Monitoring | `canary` | `src/monitoring/canary/` | `tests/lifecycle/`, `tests/tracker/`, `tests/tools/` |
| System utilities | `system` | `src/system-utilities/system/` | `tests/h848_uninstall_test.sh` |
| System utilities | `termlay` | `src/system-utilities/termlay/` | `tests/TermlayTest.py` |
| System utilities | `connect-vps` | `src/system-utilities/connect-vps/` | `tests/ConnectVpsTest.py` |
| Server services | `system-update` | `src/server-services/system-update/` | `tests/update_system_test.sh` |
| Server services | `ubuntu-updates` | `src/server-services/ubuntu-updates/` | `tests/ubuntu_updates_test.sh` |
| Server services | `vps-gateway` | `src/server-services/vps-gateway/` | `tests/vps_gateway_test.sh` |

`configuration/install.json` maps stable IDs to manifests. Manifests own categories, subcategories, commands, scopes, and hooks. Root `main.sh` chooses the canonical action scripts in `scripts/`, which dispatch through `installer/main.py`. The update workflow refreshes only registered modules and installed components, rebuilds generated commands, and verifies installed hashes; it can offer an optional `post_update` configuration prompt in interactive local runs, currently used by Canary's SSH watcher. `installer/catalog/` validates manifests, `selection/` handles choices and inventory, `core/` owns shared registry/file/profile operations, `setup/`, `update/`, and `uninstall/` own their lifecycles, `remote/` owns SSH deployment, and `portable/` owns the one canonical helper included in temporary SSH archives. Installer tests cover routing, components, and SSH bundle portability. The `system` module has independently selectable `amd-gaming` and `h848-audio` components. Manual `update-system` belongs to `system-update`; shared registries with the old `system:update` entry migrate on read. Older H848 records may omit the three new companion templates until refresh.

Module directories no longer contain portable helper copies and require the repository installer for local setup and removal. Their `setup.sh` and `uninstall.sh` paths link to `installer/module_entry.sh`; the router preserves direct module commands and local component names for `system`. SSH deployment bundles the one canonical `installer/portable/` helper with the selected module in a temporary archive; the portability test exercises those archives. Shared and remote portable registries are distinct. Both track installed command ownership; root uninstall checks the user and system shared registries and installed files. Generated state stays outside Git.

Shared installs, portable installs, and local remote-deployment records serialize mutations through the same per-scope registry lock. Capture rotation, stop, and list serialize through one capture-registry lock across profiles. Installer concurrency and profile-symlink rejection are covered by `installer/tests/lifecycle/concurrency_test.py`.

`termlay` exposes `save`, `update`, `delete`, and `list` (`ls`). The first three require an interactive terminal; `list` prints sorted saved names without prompting. Save selects tabs from the focused Ptyxis window and prompts for a new name; update selects one saved layout and replacement tabs; delete selects saved layouts and confirms removal. Capture reads tabs through AT-SPI, resolves standard shell titles and uniquely matched local foreground processes, and prompts for any remaining tab directory. It strips running-command suffixes from shell titles. Identical foreground commands can be distinguished by a matching workspace label (`task | workspace`) among their Ptyxis-owned working directories; unmatched or ambiguous labels retain manual fallback. Layouts record directories but Termlay no longer reopens them.
Its `scripts/layout/` and `scripts/ptyxis/` directories split storage from terminal integration. Each class has a PascalCase file; function modules keep path validation, accessibility reading, process lookup, and capture flow separate.

`connect-vps` is an interactive SSH picker installable in user or system scope. Each caller has a separate SQLite database. `add`, `update`, and `delete` manage named IP addresses in `$XDG_DATA_HOME/connect-vps/connections.sqlite3`; no subcommand selects and connects. Key authentication defaults to OpenSSH identities/agent when the private key path is blank. Password mode delegates the prompt to SSH and stores no secret. The module uses private 0700/0600 storage and preserves the database on uninstall.

The root wrapper also accepts `--ssh TARGET` for module and component setup/removal. It sends a portable module bundle, records successful remote deployments in the local user registry, and scans the target's portable state for selection and status. Remote removal still runs the module's portable hash checks. Network capture accepts named profiles plus port and IPv4 subnet filters; its module-owned capture registry records settings and checks whether the recorded PID is active.

VPS-Gateway can initialize its HTTP core, proxy headers, and catch-all without a site using `vps-gateway-init --empty` or the interactive `core-only` choice. The first-run and add-site wizards also offer blueprint generation or `import-existing`, which copies a project NGINX site config unchanged and validates it before reload. `vps-gateway-site-import --host NAME --file PATH|- [--replace]` supports noninteractive project deployments after empty initialization; replacements retain a private backup. Generated sites use the shared `vps_gateway` query-free access-log format; imported configs own their logging policy.

Use the validation commands in the root README and avoid live host operations when testing. See `REPOSITORY_SPRING_CLEANING.md` for the structure and future change checklist.

`log-scout` is a read-only prototype for bounded journal/text scans, category summaries, repeated-message groups, and cached examples. Its CLI composes pure scan/source/rule/view functions with `LogScoutCache.py`; schema-v1 snapshots remain private under the XDG cache directory. Unknown formats are refused, incomplete coverage is visible, and uninstall preserves cached results. Tests use synthetic logs and a real pseudo-terminal, not host logs.

`python3 installer/verify.py` runs the isolated syntax, ShellCheck, module, and
installer suites; `.github/workflows/verify.yml` uses it for Python 3.9/3.14.
`installer/tests/lifecycle/recovery_test.py` covers shared/portable Ctrl+C rollback
and failed uninstall publication/deletion. Removal restores managed files and
state per module, but does not reverse completed host removal-hook effects.
Canary's `CanaryLifecycleTest.py` verifies failed/interrupted configuration cleanup.
Canary's `scripts/ssh/` owns SSH journal classification, the watcher, and service lifecycle. Interactive local setup/update offer optional SSH event and login-account choices; scripted and remote updates only refresh installed commands. The watcher records selected journal messages in private JSONL and supports all accounts or one named login. `tests/ssh/` covers parsing, filtering, and isolated setup/update/removal.

`selection/inventory.py` and `selection/installed.py` share update/uninstall scope discovery and selectors. Explicit user updates avoid system-registry reads. SSH updates use portable `update` under the scope lock and refuse missing installations. `tests/update_test.py` covers update ownership and component preservation.
