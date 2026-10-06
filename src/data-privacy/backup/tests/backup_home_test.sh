#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

mkdir -p "$test_dir/homes/sampleuser" "$test_dir/archives" "$test_dir/mock"
printf 'first version\n' >"$test_dir/homes/sampleuser/data.txt"
export BACKUP_SOURCE_ROOT="$test_dir/homes"
export BACKUP_ROOT="$test_dir/archives"

script="$project_root/src/data-privacy/backup/scripts/snapshot/backup_home.sh"
"$script" sampleuser
destination="$BACKUP_ROOT/sampleuser"
first_archive=$(readlink -f "$destination/latest.tar.bz2")
[[ -f "$first_archive" ]]
[[ "$(stat -c %a "$destination")" == 700 ]]
[[ "$(tar -xOjf "$first_archive" ./data.txt)" == 'first version' ]]

printf 'second version\n' >"$test_dir/homes/sampleuser/data.txt"
"$script" sampleuser
second_archive=$(readlink -f "$destination/latest.tar.bz2")
[[ "$first_archive" != "$second_archive" && -f "$first_archive" ]]
[[ "$(tar -xOjf "$second_archive" ./data.txt)" == 'second version' ]]
[[ "$(tar -xOjf "$first_archive" ./data.txt)" == 'first version' ]]

cat >"$test_dir/mock/tar" <<'MOCK_TAR'
#!/usr/bin/env bash
if [[ "${1:-}" == -cjf ]]; then
    exit 13
fi
exec /usr/bin/tar "$@"
MOCK_TAR
chmod +x "$test_dir/mock/tar"
if PATH="$test_dir/mock:$PATH" "$script" sampleuser >/dev/null 2>&1; then
    echo 'Expected failed archive creation to fail' >&2
    exit 1
fi
[[ "$(readlink -f "$destination/latest.tar.bz2")" == "$second_archive" ]]
[[ -f "$first_archive" && -f "$second_archive" ]]
shopt -s nullglob
snapshots=("$destination"/backup_home_sampleuser_*.tar.bz2)
temporary=("$destination"/.backup.*.tar.bz2)
[[ ${#snapshots[@]} -eq 2 && ${#temporary[@]} -eq 0 ]]

# Pruning is a separate, explicit workflow; the latest two snapshots survive.
old_archive="$destination/backup_home_sampleuser_2020-01-01T000000.000000000_1.tar.bz2"
older_archive="$destination/backup_home_sampleuser_2020-02-01T000000.000000000_2.tar.bz2"
touch "$old_archive" "$older_archive"
"$project_root/src/data-privacy/backup/scripts/snapshot/backup_home_prune.sh" sampleuser --yes >/dev/null
[[ ! -e "$old_archive" && ! -e "$older_archive" ]]
[[ -f "$first_archive" && -f "$second_archive" ]]

if "$script" '' >/dev/null 2>&1; then
    echo 'Expected empty user name to fail' >&2
    exit 1
fi
if "$script" '../sampleuser' >/dev/null 2>&1; then
    echo 'Expected unsafe user name to fail' >&2
    exit 1
fi
if BACKUP_ROOT="$test_dir/homes/sampleuser/inside" "$script" sampleuser >/dev/null 2>&1; then
    echo 'Expected a destination inside the source to fail' >&2
    exit 1
fi

# A failed remote copy leaves the previous destination intact; a successful
# copy retains that directory as a rollback.
fetch_script="$project_root/src/data-privacy/backup/scripts/remote/fetch_remote_backup.sh"
remote_destination="$test_dir/remote-backup"
remote_source="$test_dir/remote-source"
mkdir -p "$remote_destination" "$remote_source"
printf 'old\n' >"$remote_destination/data.txt"
printf 'new\n' >"$remote_source/data.txt"
cat >"$test_dir/mock/scp" <<'MOCK_SCP'
#!/usr/bin/env bash
[[ "${MOCK_SCP_FAIL:-}" != 1 ]] || exit 13
cp -a -- "$MOCK_REMOTE_SOURCE" "${@: -1}"
MOCK_SCP
chmod +x "$test_dir/mock/scp"
export REMOTE_BACKUP_SOURCE='example.invalid:/production'
export REMOTE_BACKUP_DESTINATION="$remote_destination"
export MOCK_REMOTE_SOURCE="$remote_source"
if MOCK_SCP_FAIL=1 PATH="$test_dir/mock:$PATH" "$fetch_script" >/dev/null 2>&1; then
    echo 'Expected failed remote copy to fail' >&2
    exit 1
fi
[[ "$(cat "$remote_destination/data.txt")" == old ]]
PATH="$test_dir/mock:$PATH" "$fetch_script" >/dev/null
[[ "$(cat "$remote_destination/data.txt")" == new ]]
rollbacks=("$test_dir"/remote-backup.rollback.*)
[[ ${#rollbacks[@]} -eq 1 ]]
[[ "$(cat "${rollbacks[0]}/data.txt")" == old ]]

printf 'Backup tests passed\n'
