# Ubuntu automatic updates

This module adapts the policy and workflows from the former separate `ubuntu-unattended-upgrades` project. It uses Ubuntu's native `unattended-upgrades` and APT timers. It supports Ubuntu hosts with systemd and requires `apt`, `systemctl`, `flock`, and `sudo` for host changes. It does not create another schedule.

Install the command system-wide from the repository root with `./main.sh setup --module ubuntu-updates` or `sudo ./main.sh setup --system --module ubuntu-updates`. For remote deployment, use `./main.sh setup --ssh TARGET --system --module ubuntu-updates` from the repository root. The root setup UI automatically selects system scope for this module. Installation alone does not change APT policy, timers, or packages. The command works from any directory:

```bash
ubuntu-updates                             # interactive menu
ubuntu-updates-status                       # no sudo needed
ubuntu-updates-logs                         # readable logs only
ubuntu-updates-configure                    # interactive policy choices
ubuntu-updates-configure --updates security --reboot off --yes
ubuntu-updates-configure --updates all --reboot 04:00 --yes
ubuntu-updates-dry-run
ubuntu-updates-run                           # asks before installing updates
ubuntu-updates-run --yes                     # explicit noninteractive run
ubuntu-updates-restore                       # asks before restoring policy
```

`ubuntu-updates` keeps its original subcommands for existing scripts.

`configure` installs `unattended-upgrades` if absent, writes `/etc/apt/apt.conf.d/99-shell-scripts-unattended-upgrades`, and enables Ubuntu's existing `apt-daily.timer` and `apt-daily-upgrade.timer`. Security mode permits official Ubuntu and ESM security origins; `all` also permits official `-updates`. PPAs, proposed, and backports are excluded from unattended installation. Automatic reboot is off unless a time is explicitly supplied, and logged-in users block an automatic reboot. `dry-run` uses the current package lists; `run` refreshes them and installs allowed updates. Package changes made by `run` are not reversible by this module.

The root-owned state at `/var/lib/shell-scripts/ubuntu-updates/state.cfg` records the policy hash and the timers' enabled and active states from the first configuration. Reconfiguration verifies the current policy and keeps private revision copies there. A failed activation restores the previous policy and timer state. `restore` and `./main.sh uninstall --module ubuntu-updates` remove an unchanged owned policy and restore recorded timer states; root uninstall discovers its system registry entry and uses sudo when needed. They leave installed packages and updates in place. Locally edited or pre-existing policy files are preserved and block automatic replacement or removal. Private policy revisions remain for manual recovery.

The old standalone tool's `/etc/apt/apt.conf.d/99-cybersec-auto-updates` policy is not migrated automatically. Restore it with the standalone tool before configuring this module. To test safely, run `bash src/server-services/ubuntu-updates/tests/ubuntu_updates_test.sh`; it uses a temporary root and mocked APT/systemd commands.
