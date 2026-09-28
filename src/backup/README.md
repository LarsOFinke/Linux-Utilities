# Home backup and remote copy

From the repository root, install with `src/backup/setup.sh` or `./setup.sh --module backup`. If this module directory is copied elsewhere, run `./setup.sh` and `./uninstall.sh` inside it. Add `--system` and use sudo when root cron jobs need the commands. Copied modules use their own installation state and require Python 3.9 or newer.

## Home snapshots

`backup-home NAME` makes a verified, uniquely named archive for `/home/NAME` and offers interactive cleanup of older months while retaining the two newest snapshots. `backup-home-cron NAME` performs the same creation without prompts. Set `BACKUP_SOURCE_ROOT` for another home root and `BACKUP_ROOT` for another destination; see `configuration/backup.env.example`.

Each run writes a private temporary archive, verifies it, publishes a unique snapshot, and atomically updates `latest.tar.bz2`. A failed run leaves earlier snapshots and the latest pointer intact. Concurrent runs for one account are blocked. A destination inside the source home is rejected.

For rollback, inspect an older archive with `tar -tjf <archive>`, then extract it to an empty recovery directory with `tar -xjf <archive> -C <recovery-directory>`. Check recovered files before copying them into a live home. The commands need `tar` with bzip2 support, `flock`, GNU coreutils, and permission to read the source and write the destination.

System-wide setup installs the inactive template at `/etc/cron.d/backup-home`; edit it to enable a schedule and set the account name. Uninstall tracks this file and requires `--force` if it has been edited. Test snapshot and rollback behavior with `bash src/backup/tests/backup_home_test.sh`.

## Remote copy

`fetch-remote-backup` copies the remote directory specified by `REMOTE_BACKUP_SOURCE` to `REMOTE_BACKUP_DESTINATION` with `scp`. It stages the copy beside the destination. On success, the previous destination is kept under a unique `.rollback.<timestamp>` name. If publishing fails, the previous destination is restored. Run with the SSH identity and filesystem access intended for the remote host; the command does not invoke `sudo`. Reinstalling this module removes its old, project-specific fetch command when the installed copy is unchanged; set the new `REMOTE_BACKUP_*` variables for the renamed command.
