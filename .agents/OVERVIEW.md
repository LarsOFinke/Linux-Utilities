# Overview

The repository root provides the shared setup and uninstall interface. `src/installation/` owns the catalog, registry, transactions, and menus. Independent modules live in `src/modules/<concern>/<module>/`, each with its own manifest, setup, uninstall, README, commands, and tests.

- `data-privacy/`: backup snapshots and privacy retention.
- `monitoring/`: network capture and canary file events.
- `system-utilities/`: workstation setup with separately managed AMD gaming and H848 audio components, plus Ptyxis terminal layouts through `termlay`.
- `server-services/`: manual APT updates, unattended upgrades, and VPS gateway services.

The wrapper can deploy a module locally or over SSH; a copied module must still install and uninstall on its own. Registries live outside Git and record owned files. See `REPOSITORY_SPRING_CLEANING.md` for architecture and migration rules.
