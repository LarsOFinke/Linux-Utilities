# Onboarding

1. Read `README.md`, the relevant module README, and `PROJECT_CACHE.md`.
2. Check `git status --short` before editing. Preserve unrelated work.
3. Edit within the owning module under `src/modules/<concern>/<module>/`. Put scripts in `scripts/` or cohesive `components/`, examples in `configuration/`, and behavioral tests in `tests/`. Each module has `setup.sh`, `uninstall.sh`, and `module.json`. Update its manifest when commands, scopes, build steps, or lifecycle hooks change. Root `configuration/install.json` lists module paths and shared destinations. Generated registries are machine state, not source files.
4. Keep local values in environment variables or `.env` files. Commit only `.env.example` templates. Use `.cfg` for non-secret structured settings when an environment file is unsuitable; use JSON or JSONL for larger structured data.
5. Run Bash syntax and ShellCheck on changed scripts, plus relevant module tests and the copy-out portability test. Test setup/uninstall only with temporary HOME or install root; do not run real packet capture, live backups, or log cleanup for validation.
6. Update module documentation and `PROJECT_CACHE.md` when interfaces or structure change.
