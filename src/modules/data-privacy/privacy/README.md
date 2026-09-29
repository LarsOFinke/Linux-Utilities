# History and log cleanup

Install from the repository root with `src/modules/data-privacy/privacy/setup.sh` or `./setup.sh --module privacy`. A copied module directory has its own `./setup.sh` and `./uninstall.sh`; run `privacy-cleanup configure` after standalone setup. Repository setup offers to configure retention interactively; `--no-configure` leaves that step for later. Its default mode acts only on the current user's files and needs no sudo:

The daily user schedule requires `crontab` and a running cron service.

`privacy-cleanup` remains available with its original subcommands. The managed schedule calls `privacy-scheduled`; removal uses `privacy-uninstall-schedule`.

```bash
privacy-configure
privacy-status
privacy-run --dry-run
privacy-run
```

`configure` interactively sets the Bash-history clearing interval, the retention age for `*.log` and `*.log.*` files under a chosen directory inside your home, and the daily run time. It writes `~/.config/privacy-cleanup/user.cfg` and adds one marked entry to your existing crontab. It backs up the previous crontab before changing it. Other crontab entries are preserved. A manual `run` immediately applies every enabled user category and asks for a typed confirmation; `run --yes` is for intentional non-interactive use. The scheduled pass clears Bash history only when its interval has elapsed.

For host logs, install the command system-wide with `sudo ./setup.sh --system --module privacy`, then configure and run the optional root mode:

```bash
sudo privacy-configure --system
sudo privacy-run --system --dry-run
sudo privacy-run --system
```

System mode writes `/etc/privacy-cleanup/system.cfg` and `/etc/cron.d/privacy-cleanup`. It asks for journal, rotated cron, login (`wtmp`/`btmp`), and other rotated system-log retention. It uses `journalctl --rotate --vacuum-time=<days>d` and deletes only matching rotated files older than the selected age. Active log files remain under the distribution's logrotate policy. Cron messages inside the journal follow journal retention; cron messages inside `syslog` follow system-log retention. `last` and `lastb` use `wtmp` and `btmp`; the separate `lastlog` database is not changed.

Zero days disables a category. Policy files are parsed as data rather than executed as shell code. The manual command applies the configured ages; it does not erase every current record. Bash history has no reliable per-entry age when timestamps are absent, so its interval clears the whole file. An open shell can later write its in-memory history back; close other shells before a manual history cleanup if complete clearing matters.

`./uninstall.sh --module privacy` removes the installed command and its managed schedule. It preserves the policy file by default; add `--purge-config` to delete it too. See the root README for installation and registry details.
