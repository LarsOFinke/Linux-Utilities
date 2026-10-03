"""CLI composition boundary for scanning, cached inspection, and cache removal."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from LogScoutCache import LogScoutCache
from log_scout_rules import CATEGORIES, sanitize
from log_scout_scan import scan
from log_scout_view import browse, details, summary


def cache_directory() -> Path:
    override = os.environ.get("LOG_SCOUT_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "linux-utilities/log-scout"


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Read-only Linux log triage: scan → categories → finding details.")
    commands = cli.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("scan", help="Scan and cache a summary; browse when running in a terminal")
    collect.add_argument("--file", action="append", default=[], type=Path, help="Plain text log; repeat up to 16 times")
    collect.add_argument("--journal", action="store_true", help="Also read the journal when --file is used")
    collect.add_argument("--since", default="24 hours ago", help="Journal time window only (default: 24 hours ago)")
    collect.add_argument("--limit", type=int, default=5000, help="Newest entries per source, 1–10000 (default: 5000)")
    collect.add_argument("--no-interactive", action="store_true")
    collect.add_argument("--json", action="store_true", help="Emit the redacted snapshot as JSON")
    for name in ("summary", "details", "browse"):
        sub = commands.add_parser(name, help=f"Show cached {name}; does not rescan logs")
        sub.add_argument("--scan", default="latest", help="Scan ID from history, or latest")
        if name == "summary":
            sub.add_argument("--json", action="store_true")
        if name == "details":
            sub.add_argument("category", choices=CATEGORIES)
            sub.add_argument("--group", type=int, help="Show examples for one numbered group")
            sub.add_argument("--offset", type=int, default=0)
            sub.add_argument("--limit", type=int, default=20)
    commands.add_parser("history", help="List retained scan IDs and coverage")
    purge = commands.add_parser("purge-cache", help="Delete this tool's recognized cached snapshots, never source logs")
    purge.add_argument("--yes", action="store_true", required=True)
    return cli


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args((sys.argv[1:] if argv is None else argv) or ["scan"])
    try:
        cache = LogScoutCache(cache_directory())
        if args.command == "scan":
            print("Scanning selected logs…", file=sys.stderr)
            data = scan([path.expanduser().absolute() for path in args.file], args.journal or not args.file,
                        args.since, args.limit)
            cache.save(data)
            if args.json:
                print(json.dumps(data, ensure_ascii=True, indent=2))
            else:
                summary(data)
                print(f"Saved privately. Reopen: log-scout summary --scan {data['id']}")
                if not args.no_interactive and sys.stdin.isatty() and sys.stdout.isatty():
                    browse(data)
            return 2 if data["partial"] else 0
        if args.command == "history":
            scans = cache.history()
            for data in scans:
                print(f"{data['id']}  {data['created_at']}  {data['matches']} matches  "
                      f"{'partial' if data['partial'] else 'bounded'}")
            if not scans:
                print("No cached scans; run log-scout scan.")
        elif args.command == "purge-cache":
            print(f"Removed {cache.purge()} cached scans.")
        else:
            data = cache.load(args.scan)
            if args.command == "details":
                if args.offset < 0 or not 1 <= args.limit <= 100:
                    raise ValueError("Use a nonnegative --offset and --limit between 1 and 100")
                details(data, args.category, args.offset, args.limit, args.group)
            elif args.command == "summary" and args.json:
                print(json.dumps(data, ensure_ascii=True, indent=2))
            else:
                summary(data)
                if args.command == "browse":
                    browse(data)
        return 0
    except KeyboardInterrupt:
        print("Cancelled; completed cached scans remain available.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError) as error:
        print(f"log-scout: {sanitize(error)}", file=sys.stderr)
        return 1
