#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=src/data-privacy/backup/scripts/snapshot/backup_home_common.sh
source "${SCRIPT_DIR}/backup_home_common.sh"

backup_home_run "${1:-}"
