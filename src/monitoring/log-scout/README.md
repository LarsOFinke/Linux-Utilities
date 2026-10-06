# Linux log triage (`log-scout`) — prototype

A read-only terminal utility for **scan → summary → category → repeated-message group → examples**.
It reads the journal or explicitly selected plain text logs, counts warnings/errors, groups
similar messages, and saves private snapshots for later inspection without rescanning.
It does not change logs, start services, send data, or repair a host.

## Install and use

```bash
./main.sh setup --module log-scout
log-scout                                  # scan journal, summarize, then browse in a terminal
log-scout scan --since '2 hours ago' --limit 5000
log-scout scan --file /var/log/syslog --file /var/log/auth.log
log-scout scan --journal --file /path/to/app.log --no-interactive
log-scout summary                          # latest cached scan, no source reads
log-scout details network                  # numbered groups, newest cached scan
log-scout details network --group 1         # representative messages
log-scout details services --offset 20      # next page
log-scout browse                           # reopen the interactive category/group menu
log-scout history                          # scan IDs and coverage
log-scout summary --scan SCAN_ID --json
log-scout purge-cache --yes                 # delete recognized cache snapshots only
./main.sh uninstall --module log-scout
```

In the interactive view, select a category by number or name, then a numbered message
group. `n`/`p` change pages, `b` returns to categories, and `q` exits. Noninteractive
execution prints the summary and exits. `--json` emits the redacted snapshot without a menu.
`scan` always creates a new snapshot; `summary`, `details`, `browse`, and `history` use cache.
Cached timestamps are displayed so an old snapshot is not confused with a fresh scan.

Python 3.9+ is required. Journal scans also require `journalctl`; file scans need only
Python. Existing access permissions apply. The tool never invokes sudo; use an account
with the intended journal/log access. Running it under sudo uses that account's cache.
Installation supports user or `--system` command scope without scanning or changing the
host. Module setup and removal require the repository installer.
Uninstall preserves cached scans. Clear them explicitly before uninstall if desired.

## Scope and limits

- Default: newest 5,000 accessible journal entries within the last 24 hours. `--since`
  applies **only to the journal**. Explicit `--file` selections replace the journal unless
  `--journal` is also given. Text files are read from their end, without timestamp filtering.
- Up to 16 text logs; 1–10,000 entries per source. Each file reads at most its last 8 MiB.
  Journal stdout and stderr together are capped at 8 MiB, with a 20-second timeout.
  Directories, symlinks, devices, FIFOs, binary and compressed logs are refused.
- Journal priority 0–2 maps to critical, 3 to error, and 4 to warning. Priorities 5–7 are
  ignored even if their messages mention errors. Plain text uses keyword heuristics.
  Categories are memory, storage, security, network, services, kernel, and other;
  overlapping matches use this precedence. These are triage hints, not diagnoses.
- Groups combine category, severity, source, unit, and a message pattern with numbers and
  selected IDs normalized. A scan stores at most 250 groups with two examples per group;
  messages are limited to 2,048 characters. Counts include matches omitted from details.
  Multiline text stack traces are not reconstructed; JSON journal messages remain one entry.
- Summary coverage lists failed sources, journal diagnostics, and entry/byte/detail caps.
  An empty accessible journal does not prove the whole host is healthy. Permissions can
  hide additional journals. Scanning a journal and its mirrored text log counts both copies.
- Exit codes: `0` completed operation (findings are not failures), `1` failure, `2` partial
  scan or CLI usage error, `130` cancellation. Cached inspection returns `0` even when
  the selected scan records partial coverage. When every source fails, no new cache is
  published and the last successful scan remains available.

## Cached data and privacy

Snapshots live under `$XDG_CACHE_HOME/linux-utilities/log-scout`, defaulting to
`~/.cache/linux-utilities/log-scout`. `LOG_SCOUT_CACHE_DIR` overrides that location and
must be absolute. See `configuration/cache.env.example`; it is documentation, not a
sourced configuration file.

Directories must be private (0700) and owned by the current account; snapshot files use
0600. Cache writes are serialized and published atomically. Schema version 1 includes
scan identity/time, rule version, scan options, source coverage, category counts, grouped
findings, and bounded redacted examples. No raw journal dump is stored. Common password,
token, secret, API-key, bearer-token, URL-credential/query, and email patterns are masked;
terminal control characters are removed. Redaction is best effort: paths, usernames,
addresses, and unknown secret formats may remain. Treat cached diagnostics as private.

After each successful publication, recognized snapshots older than seven days or beyond
the newest ten are removed. This is lazy retention: unused caches remain until the next
scan or explicit purge. Invalid/future-format snapshots are preserved; inspection reports
an error instead of silently treating them as valid. `purge-cache --yes` validates the
whole recognized selection first and leaves unrelated files alone. Cache data is not an
installation registry and never belongs in Git.

## Architecture and verification

This module follows AI-Project-Toolkit's `MODULAR_UTILITIES` profile and shared quality
standards, adapted to the existing repository. The dependency direction is CLI → scan
rules/source adapters and cache; terminal rendering does not own collection or persistence.
`LogScoutCache.py` owns the versioned storage contract. Pure functions own source reads,
classification, grouping, and presentation. Only Python's standard library is needed.

Acceptance criteria: bounded scan, visible coverage, correct category counts, reopenable
private snapshots, category/group drill-down, previous-cache preservation on failed scans,
controlled retention, and shared installer setup/removal from any working directory.

```bash
python3 src/monitoring/log-scout/tests/LogScoutTest.py
python3 installer/tests/portable/portable_modules_test.py
```

Tests use synthetic text/journal fixtures, temporary cache/install roots, mocked journalctl,
and a real pseudo-terminal for menu interaction. They cover redaction, bounds, failures,
cache schema/privacy/retention, and lifecycle ownership. Real journal coverage on a
representative host remains an integration check; this delivery is a prototype, not a
release-readiness claim. No monitoring daemon, automatic remediation, compressed-log
reader, incremental cursor, or external AI service is part of this first slice.

Verification for this prototype was performed on Linux with Python 3.14.4: the focused
command above passed 14 behavior/lifecycle tests, including actual pseudo-terminal input.
The repository's documented Bash syntax, ShellCheck, installation, portability, routing,
and module suites passed (the routing test was updated for the new catalog and rerun).
Python 3.9 grammar parsing passed; execution on a Python 3.9 interpreter was not performed.
Live host journal coverage was not tested; journal transport tests used synthetic subprocesses.
