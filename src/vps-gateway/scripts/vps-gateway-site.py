#!/usr/bin/env python3
"""Render site blueprints and launch the first-run gateway wizard."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from vps_site_add import add
from vps_site_init import init
from vps_site_model import BLUEPRINTS, document_root, hostname, port, render_site

# The install-time builder replaces these markers with embedded templates.
TEMPLATES = None
CORE_TEMPLATES = None

def templates() -> dict[str, str]:
    if TEMPLATES is not None:
        return TEMPLATES
    base = Path(__file__).resolve().parents[1] / "configuration" / "blueprints"
    return {name: (base / f"{name}.conf.example").read_text(encoding="utf-8") for name in BLUEPRINTS}


def core_templates() -> dict[str, str]:
    if CORE_TEMPLATES is not None:
        return CORE_TEMPLATES
    base = Path(__file__).resolve().parents[1] / "configuration" / "core"
    return {name: (base / f"{name}.conf.example").read_text(encoding="utf-8")
            for name in ("http", "proxy-headers", "catch-all")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="list available blueprints")
    subcommands.add_parser("init", help="interactively install the first gateway site")
    subcommands.add_parser("add", help="interactively add a site to the initialized gateway")
    render = subcommands.add_parser("render", help="render a site to stdout or a new file")
    render.add_argument("blueprint", choices=BLUEPRINTS)
    render.add_argument("--host", type=hostname, required=True)
    render.add_argument("--port", type=port)
    render.add_argument("--root", type=document_root)
    render.add_argument("--output", type=Path, help="create this file; refuses to overwrite")
    args = parser.parse_args(argv)

    if args.command == "list":
        for name in BLUEPRINTS:
            print(name)
        return 0

    if args.command == "init":
        try:
            return init(templates(), core_templates())
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled.", file=sys.stderr)
            return 1
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"First-run setup failed: {error}", file=sys.stderr)
            return 1

    if args.command == "add":
        try:
            return add(templates())
        except (EOFError, KeyboardInterrupt):
            print("\nSite addition cancelled.", file=sys.stderr)
            return 1
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"Site addition failed: {error}", file=sys.stderr)
            return 1

    example_host, example_port, example_root = BLUEPRINTS[args.blueprint]
    if example_port is not None and (args.port is None or args.root is not None):
        parser.error("this blueprint requires --port and does not accept --root")
    if example_root is not None and (args.root is None or args.port is not None):
        parser.error("this blueprint requires --root and does not accept --port")

    result = render_site(templates(), args.blueprint, args.host, args.port, args.root)

    if args.output is None:
        sys.stdout.write(result)
    else:
        try:
            descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(result)
        except OSError as error:
            parser.error(f"cannot create {args.output}: {error}")
        print(f"Created {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
