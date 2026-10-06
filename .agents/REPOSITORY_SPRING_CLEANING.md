# Repository spring cleaning

## Architecture

The repository is a wrapper around modules. Root `main.sh` selects setup, update, or uninstall from `scripts/`; those scripts call `installer/main.py` for discovery, scope routing, transactions, and registry based ownership. `configuration/install.json` is the single map from stable module IDs to manifests. Module setup and removal require the repository installer; SSH deployment adds the canonical portable helper to a temporary archive.

Modules live under `src/<concern>/<module>/`. The concern directories are `data-privacy`, `monitoring`, `system-utilities`, and `server-services`. Each module owns `module.json`, `README.md`, `setup.sh`, `uninstall.sh`, scripts or components, and focused tests. A manifest carries a category and a subcategory for navigation; those labels may change without changing the stable ID. Use a component in a module only when the tasks share a cohesive purpose and need independently selectable install ownership.

Keep Python modules small and grouped by concern. Add subdirectories for cohesive areas such as `layout/` and `ptyxis/` when they make ownership clearer. Give each class its own matching `PascalCase.py` file, including test classes; put related standalone functions in descriptive `snake_case.py` files. Update test discovery patterns when renaming test class files. Keep dependencies one way and remove unused abstractions. When splitting installed scripts, list every helper in the module manifest and verify that installed commands still work from any directory.

In `installer/`, keep manifest validation in `catalog/`, discovery and scope routing in `selection/`, reusable registry/file/profile operations in `core/`, lifecycle behavior in `setup/`, `update/`, and `uninstall/`, SSH deployment in `remote/`, and the single canonical SSH helper in `portable/`. Keep `main.py` as the shared transaction entry point. Preserve the lock across the whole transaction and preserve rollback coverage when moving code. A file's length is a prompt to review its responsibilities, not a reason to split a cohesive algorithm. Use classes for stateful objects and functions for stateless workflows.

The `system` module contains the `amd-gaming` and `h848-audio` components. Manual APT updates moved to `server-services/system-update` as an independent module. `ubuntu-updates` owns unattended upgrade policy and remains distinct. `backup` separates snapshot and remote scripts. Other modules keep their own internal structure because their files already belong to one concern.

## Ownership and migration

Registry entries identify installed commands by path and hash. Shared uninstall reads both user and system registries, verifies the installed files, and removes only owned paths. The prior `system:update` registry record is translated to `system-update` when loaded; its `update-system` command remains removable without reinstalling. Existing stable module IDs, command names, registry locations, and remote portable state remain the compatibility boundary. Do not infer removal solely from the current source tree.

## Adding or moving a module

1. Put its source directory under the appropriate concern. Update its manifest, README, and direct entry points.
2. Add or change its manifest path in `configuration/install.json`. Keep the ID stable when only moving files. If ownership changes, provide a registry migration.
3. Update source paths used by commands, build hooks, templates, and tests. Add any new SSH helper dependencies to `installer/remote/deploy.py`.
4. Test direct setup/uninstall, root setup/update/uninstall in both supported scopes, partial component ownership if present, and the temporary SSH archive. Use temporary HOME and install roots.
5. Update the root README and `PROJECT_CACHE.md`. Keep secrets, local settings, build output, and generated state out of Git.

## Final sweep

After moving a module or component, inspect the old location and remove empty directories and generated caches. Search manifests, scripts, tests, and documentation for stale source paths and old ownership names. Keep references to retired names only where they explain or implement compatibility migration. Check `git status --short --untracked-files=all` for stray generated files, then run the focused lifecycle tests, Bash syntax checks, ShellCheck, and `git diff --check` before committing.

Use `scripts/clean-cache.sh --dry-run` to preview generated Python and test caches under `installer/`, `src/`, and `scripts/`; run it without the flag to remove them. It does not touch registries, backups, or installed state.

See `ONBOARDING.md` and `QUALITIES.md` for routine changes and required qualities.
See `CLEANUP_AUDIT.md` for the repository-wide file assessment and remaining split candidates.
