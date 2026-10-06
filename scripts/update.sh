#!/usr/bin/env bash
set -Eeuo pipefail
repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$repository/installer/main.py" select-update "$@"
