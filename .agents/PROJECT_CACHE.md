# Project cache

Read this first for the short map, then the relevant module README.

| Module (stable ID) | Commands | Source | Focused test |
| --- | --- | --- | --- |
| Home backup (`backup`) | `backup-home`, `backup-home-cron`, `fetch-remote-backup` | `src/backup/` | `src/backup/tests/backup_home_test.sh` |
| Packet capture (`network`) | `capture-traffic` | `src/network/` | `src/network/tests/capture_traffic_test.sh` |
| Desktop hardware (`system`) | `install-amd-gaming`, `install-h848-audio-fix` | `src/system/` | `src/system/tests/h848_uninstall_test.sh` |
| History and logs (`privacy`) | `privacy-cleanup` | `src/privacy/` | `src/privacy/tests/privacy_cleanup_test.sh` |
| Ubuntu updates (`ubuntu-updates`) | `ubuntu-updates` | `src/ubuntu-updates/` | `src/ubuntu-updates/tests/ubuntu_updates_test.sh` |
| Canary monitoring (`canary`) | `fs-tracker`, `canary-control` | `src/canary/` | `src/canary/tests/integration_test.sh` |
| NGINX and Certbot (`vps-gateway`) | `vps-gateway` | `src/vps-gateway/` | `src/vps-gateway/tests/vps_gateway_test.sh` |
| Installation | `setup.sh`, `uninstall.sh` | `src/installation/orchestrate.py`, `manage.py` | `src/installation/tests/` |

`configuration/install.json` lists module manifest paths and shared installation scopes. Each `src/<module>/module.json` owns commands, examples, build and removal hooks, and presentation labels. `setup.sh` installs same-scope selections as one transaction through the shared registry installer. Mixed user/system selections require `--system` or separate commands. Reinstall removes unchanged obsolete owned files. Commands go to `~/.local/bin` by default or `/usr/local/bin` with `--system`. System setup also installs inactive backup/network cron templates. Root `uninstall.sh` removes selected registered modules. Copied modules use their own portable registry under `shell-scripts/portable/`.

Backup creation uses `src/backup/scripts/backup_home_common.sh`, with a lock, private verified temporary archive, unique snapshots, and an atomic latest pointer. Network rotation tracks only its own PID. The audio installer restores original files on uninstall. Privacy defaults to user-only history and user-log cleanup; `--system` is optional for journal and rotated host logs.

Ubuntu updates is system-scope only. Installing its command does not apply a policy. Its explicit `configure` records an owned APT policy hash and timer baseline; system uninstall runs its restore first. Tests use mocked APT and systemd under a temporary root.

Canary is system-scope only. Setup compiles the C sensor before the shared transaction and installs no active service. `canary-control configure` creates named, hashed systemd units and configs; module uninstall removes those services but preserves targets and event logs. Test with a temporary install root.

VPS gateway is system-scope only. Setup installs an inert command. Explicit `vps-gateway configure` installs distribution NGINX/Certbot packages and enables NGINX without owning project sites. Uninstall removes only the command and preserves packages and configuration.

Run the validation commands in the root README. Do not run live installers, packet captures, or log cleanup as a test.
The copy-out test is `src/installation/tests/portable_modules_test.py`.
