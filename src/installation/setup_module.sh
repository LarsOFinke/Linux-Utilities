#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -gt 0 ]] || { echo 'Provide a module name.' >&2; exit 2; }
module=$1
shift
repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
exec "$repository/setup.sh" --module "$module" "$@"
