# Project cache

Read this compact map first, then the relevant module README. The root setup and uninstall scripts are a wrapper over independent modules.

| Concern | Module ID | Source | Focused test |
| --- | --- | --- | --- |
| Data and privacy | `backup` | `src/modules/data-privacy/backup/` | `tests/backup_home_test.sh` |
| Data and privacy | `privacy` | `src/modules/data-privacy/privacy/` | `tests/privacy_cleanup_test.sh` |
| Monitoring | `network` | `src/modules/monitoring/network/` | `tests/capture_traffic_test.sh` |
| Monitoring | `canary` | `src/modules/monitoring/canary/` | `tests/integration_test.sh` |
| System utilities | `system` | `src/modules/system-utilities/system/` | `tests/h848_uninstall_test.sh` |
| System utilities | `termlay` | `src/modules/system-utilities/termlay/` | `tests/TermlayTest.py` |
| Server services | `system-update` | `src/modules/server-services/system-update/` | `tests/update_system_test.sh` |
| Server services | `ubuntu-updates` | `src/modules/server-services/ubuntu-updates/` | `tests/ubuntu_updates_test.sh` |
| Server services | `vps-gateway` | `src/modules/server-services/vps-gateway/` | `tests/vps_gateway_test.sh` |

`configuration/install.json` maps stable IDs to manifests. Manifests own categories, subcategories, commands, scopes, and hooks. `src/installation/` owns catalog validation, shared registry transactions, and interactive selection; its tests cover routing, components, and copied module portability. The `system` module has independently selectable `amd-gaming` and `h848-audio` components. Manual `update-system` belongs to `system-update`; shared registries with the old `system:update` entry migrate on read.

Each module directory can be copied out and installed without the repository using its synchronized `portable_module.py`. Shared and portable registries are distinct. Both track installed command ownership; root uninstall checks the user and system shared registries and installed files. Generated state stays outside Git.

`termlay save-current NAME` reads the focused Ptyxis window through AT-SPI, resolves standard shell titles and uniquely matched local foreground processes, and prompts for any remaining tab directory before saving the complete layout.
Its `scripts/layout/` and `scripts/ptyxis/` directories split storage from terminal integration. Each class has a PascalCase file; function modules keep path validation, accessibility reading, process lookup, and capture flow separate.

The root wrapper also accepts `--ssh TARGET` for module and component setup/removal. It sends a portable module bundle, records successful remote deployments in the local user registry, and scans the target's portable state for selection and status. Remote removal still runs the module's portable hash checks. Network capture accepts named profiles plus port and IPv4 subnet filters; its module-owned capture registry records settings and checks whether the recorded PID is active.

VPS-Gateway can initialize its HTTP core, proxy headers, and catch-all without a site using `vps-gateway-init --empty` or the interactive `core-only` choice. The first-run and add-site wizards also offer blueprint generation or `import-existing`, which copies a project NGINX site config unchanged and validates it before reload. `vps-gateway-site-import --host NAME --file PATH|- [--replace]` supports noninteractive project deployments after empty initialization; replacements retain a private backup. Generated sites use the shared `vps_gateway` query-free access-log format; imported configs own their logging policy.

Use the validation commands in the root README and avoid live host operations when testing. See `REPOSITORY_SPRING_CLEANING.md` for the structure and future change checklist.
