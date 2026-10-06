# Overview

Root `main.sh` provides the setup, update, and uninstall menu; `scripts/` owns the action scripts. `installer/` separates catalog validation, `selection/` discovery, `core/` registry operations, `remote/` SSH transport, one canonical portable helper for temporary SSH archives, and `setup/`, `update/`, and `uninstall/` workflows. Modules live in `src/<concern>/<module>/`, each with its own manifest, setup, uninstall, README, commands, and tests.

- `data-privacy/`: backup snapshots and privacy retention.
- `monitoring/`: network capture and canary file events.
- `system-utilities/`: workstation setup with separately managed AMD gaming and H848 audio components, Ptyxis terminal layouts through `termlay`, and SSH connection selection through `connect-vps`.
- `server-services/`: manual APT updates, unattended upgrades, and VPS gateway services.

The wrapper deploys a module locally or over SSH. A module directory copied alone has no installer; SSH archives add the canonical helper temporarily. Registries live outside Git and record owned files. See `REPOSITORY_SPRING_CLEANING.md` for architecture and migration rules.
