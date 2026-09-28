#!/usr/bin/env bash
set -Eeuo pipefail
module_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
includes=()
for directory in actions config events monitoring output process; do
    includes+=("-I$module_dir/tracker/$directory")
done
flags=(-std=gnu11 -O2 -Wall -Wextra -Wpedantic)
"${CC:-cc}" "${flags[@]}" "${includes[@]}" "$module_dir/tests/test_event_names.c" "$module_dir/tracker/events/event_names.c" -o "$test_dir/event_names"
"$test_dir/event_names"
"${CC:-cc}" "${flags[@]}" "${includes[@]}" "$module_dir/tests/test_config.c" "$module_dir/tracker/config/config.c" -o "$test_dir/config"
"$test_dir/config"
"${CC:-cc}" "${flags[@]}" "${includes[@]}" "$module_dir/tests/test_jsonl_sink.c" "$module_dir/tracker/output/jsonl_sink.c" "$module_dir/tracker/events/event_names.c" "$module_dir/tracker/process/proc_info.c" -o "$test_dir/jsonl_sink"
"$test_dir/jsonl_sink"
printf 'Canary C unit tests passed\n'
