# History and log cleanup

Setup and update need `cc` and install one ELF executable for the module. Policy, schedule, and cleanup helpers are embedded; an update removes older registry-owned helper scripts from the command directory. Python 3.9+ is needed to launch the commands. Configurations and schedules remain separate managed files.

Install from the repository root with `src/data-privacy/privacy/setup.sh` or `./main.sh setup --module privacy`. Run `privacy configure` after a noninteractive installation when you want a cleanup schedule. Repository setup offers to configure retention interactively; `--no-configure` leaves that step for later. Its default mode acts only on the current user's files and needs no sudo:

The daily user schedule requires `crontab` and a running cron service.

The managed schedule calls `privacy scheduled`; removal uses `privacy uninstall-schedule`.

```bash
privacy configure
privacy status
privacy run --dry-run
privacy run
```

`configure` interactively sets the Bash-history clearing interval, the retention age for `*.log` and `*.log.*` files under a chosen directory inside your home, and the daily run time. It writes `~/.config/privacy-cleanup/user.cfg` and adds one marked entry to your existing crontab. It backs up the previous crontab before changing it. Other crontab entries are preserved. A manual `run` immediately applies every enabled user category and asks for a typed confirmation; `run --yes` is for intentional non-interactive use. The scheduled pass clears Bash history only when its interval has elapsed.

For host logs, install the command system-wide with `sudo ./main.sh setup --system --module privacy`, then configure and run the optional root mode:

```bash
sudo privacy --system configure
sudo privacy --system run --dry-run
sudo privacy --system run
```

System mode writes `/etc/privacy-cleanup/system.cfg` and `/etc/cron.d/privacy-cleanup`. It asks for journal, rotated cron, login (`wtmp`/`btmp`), and other rotated system-log retention. It uses `journalctl --rotate --vacuum-time=<days>d` and deletes only matching rotated files older than the selected age. Active log files remain under the distribution's logrotate policy. Cron messages inside the journal follow journal retention; cron messages inside `syslog` follow system-log retention. `last` and `lastb` use `wtmp` and `btmp`; the separate `lastlog` database is not changed.

Zero days disables a category. Policy files are parsed as data rather than executed as shell code. The manual command applies the configured ages; it does not erase every current record. Bash history has no reliable per-entry age when timestamps are absent, so its interval clears the whole file. An open shell can later write its in-memory history back; close other shells before a manual history cleanup if complete clearing matters.

`./main.sh uninstall --module privacy` removes the installed command and its managed schedule. It preserves the policy file by default; add `--purge-config` to delete it too. See the root README for installation and registry details.
