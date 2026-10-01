# Qualities

- **Data safety:** Never replace a verified backup with a partial archive. Preserve older snapshots for rollback. Verify before deleting a source pcap. Keep backup and capture output private with mode 0700 directories and umask 077.
- **Scope:** A script may stop only processes it owns. Refuse ambiguous or unsafe paths and arguments.
- **Failure behavior:** Return a nonzero status on failed work, keep recoverable data, and print a useful error.
- **Reversibility:** Installers that replace user files must save originals and restore them on uninstall.
- **Maintainability:** Prefer small Bash functions, quoted expansions, `set -Eeuo pipefail` for entry points, and no duplicate core logic. Group Python code by concern, keep one class per matching `PascalCase.py` file, and use descriptive `snake_case.py` files for standalone functions.
- **Documentation:** Show concrete commands and configuration variables beside each module. Keep agent notes short enough to save context.
- **Verification:** Syntax, ShellCheck, and focused behavior tests must pass before a change is considered done.
- **Deployment:** Installed commands work from any directory. Setup and uninstall use the JSON registry to touch only owned command paths and managed schedules.
