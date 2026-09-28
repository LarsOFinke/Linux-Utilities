# Overview

Root files are `README.md`, `setup.sh`, `uninstall.sh`, `AGENTS.md`, and repository metadata. Operational modules live under `src/` and own their setup entry point, scripts, configuration examples, tests, cron templates, and README. Root setup delegates to those entry points; `src/installation/` manages command deployment and the JSON registry.

- `src/backup/`: private, verified home snapshots and a staged remote copy with rollback.
- `src/network/`: managed packet capture rotation.
- `src/system/`: Ubuntu and H848 device setup.
- `src/privacy/`: user-only scheduled cleanup by default, optional root cleanup for host logs.

Cron templates are commented examples. The privacy module generates its own schedules when configured.
