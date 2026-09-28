#!/usr/bin/env python3
"""Render a VPS gateway site from the packaged, reviewed NGINX blueprints."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# The install-time builder replaces this marker with embedded template contents.
TEMPLATES = None
CORE_TEMPLATES = None

BLUEPRINTS = {
    "http-app": ("app.example.org", "18081", None),
    "java-spring": ("java.example.org", "18083", None),
    "python-asgi": ("python.example.org", "18084", None),
    "websocket": ("socket.example.org", "18082", None),
    "static-html": ("static.example.org", None, "/srv/www/static.example.org"),
    "spa": ("spa.example.org", None, "/srv/www/spa.example.org"),
}


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


def hostname(value: str) -> str:
    value = value.lower()
    if len(value) > 253 or not re.fullmatch(r"[a-z0-9.-]+", value):
        raise argparse.ArgumentTypeError("host must be an ASCII DNS name")
    labels = value.split(".")
    if len(labels) < 2 or any(
        not label or len(label) > 63 or label[0] == "-" or label[-1] == "-"
        for label in labels
    ):
        raise argparse.ArgumentTypeError("host must be a valid DNS name")
    return value


def port(value: str) -> int:
    if not value.isascii() or not value.isdecimal() or len(value) > 5 or not 1 <= int(value) <= 65535:
        raise argparse.ArgumentTypeError("port must be an integer from 1 to 65535")
    return int(value)


def document_root(value: str) -> str:
    if not value.startswith("/") or not re.fullmatch(r"/[a-zA-Z0-9_./-]+", value):
        raise argparse.ArgumentTypeError("root must be an absolute path without spaces or NGINX metacharacters")
    if ".." in Path(value).parts:
        raise argparse.ArgumentTypeError("root must not contain '..'")
    return value.rstrip("/")


def render_site(blueprint: str, host: str, backend_port: int | None, root: str | None) -> str:
    example_host, example_port, example_root = BLUEPRINTS[blueprint]
    result = templates()[blueprint]
    if example_port is not None:
        if backend_port is None or root is not None:
            raise ValueError("this blueprint requires a port")
        result = result.replace(f"127.0.0.1:{example_port}", f"127.0.0.1:{backend_port}")
    else:
        if root is None or backend_port is not None:
            raise ValueError("this blueprint requires a document root")
        result = result.replace(example_root, root)
    return result.replace(example_host, host)


def ask(label: str, validator) -> str | int:
    while True:
        value = input(f"{label}: ").strip()
        try:
            return validator(value)
        except argparse.ArgumentTypeError as error:
            print(f"Invalid value: {error}", file=sys.stderr)


def create_file(path: Path, contents: str, created: list[Path]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    created.append(path)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(contents)


def init() -> int:
    install_root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
    if install_root == Path("/") and os.geteuid() != 0:
        raise RuntimeError("run the first-run wizard with sudo")
    print("First VPS gateway site")
    for number, name in enumerate(BLUEPRINTS, 1):
        print(f"  {number}. {name}")
    choice = ask("Blueprint number", lambda value: selected_blueprint(value))
    host = ask("Public DNS hostname", hostname)
    backend_port = None
    root = None
    if BLUEPRINTS[choice][1] is not None:
        backend_port = ask("Loopback host port", port)
    else:
        root = ask("Absolute document root", document_root)
    site_name = f"{host}.conf"
    nginx_dir = install_root / "etc/nginx"
    available = nginx_dir / "sites-available"
    enabled = nginx_dir / "sites-enabled"
    site_path = available / site_name
    core_path = nginx_dir / "conf.d/vps-gateway.conf"
    headers_path = nginx_dir / "snippets/vps-gateway-proxy-headers.conf"
    catchall_path = available / "vps-gateway-catch-all.conf"
    default_link = enabled / "default"

    print(f"\nWill install NGINX/Certbot and activate {host} from {choice}.")
    print(f"Site: {site_path}")
    print(f"Core: {core_path}")
    print("The packaged default site will be disabled and unknown hosts rejected.")
    request_tls = input("Request a TLS certificate after activation? DNS must already point here. [y/N] ").strip().lower() == "y"
    if input("Apply this first-run setup? [y/N] ").strip().lower() != "y":
        print("No changes made.")
        return 0

    subprocess.run([str(Path(__file__).with_name("vps-gateway")), "configure"], check=True)
    if not (nginx_dir / "nginx.conf").is_file():
        raise RuntimeError(f"NGINX configuration is missing: {nginx_dir / 'nginx.conf'}")
    for directory in (available, enabled, nginx_dir / "conf.d", nginx_dir / "snippets"):
        if not directory.is_dir():
            raise RuntimeError(f"NGINX directory is missing: {directory}")
    other_sites = [path.name for path in enabled.iterdir() if path.name != "default"]
    if other_sites:
        raise RuntimeError(f"first-run setup requires no other enabled sites: {', '.join(other_sites)}")
    other_conf = list((nginx_dir / "conf.d").glob("*.conf"))
    if other_conf:
        raise RuntimeError("first-run setup requires an empty /etc/nginx/conf.d; review existing config manually")
    targets = (site_path, enabled / site_name, core_path, headers_path,
               catchall_path, enabled / catchall_path.name)
    if any(path.exists() or path.is_symlink() for path in targets):
        raise RuntimeError("a gateway configuration target already exists; review it before rerunning")
    default_target = None
    if default_link.exists() or default_link.is_symlink():
        if not default_link.is_symlink():
            raise RuntimeError("sites-enabled/default is not the packaged symlink")
        default_target = os.readlink(default_link)
        if default_target not in ("/etc/nginx/sites-available/default", "../sites-available/default"):
            raise RuntimeError("sites-enabled/default has a custom target")

    created: list[Path] = []
    default_disabled = False
    try:
        core = core_templates()
        create_file(core_path, core["http"], created)
        create_file(headers_path, core["proxy-headers"], created)
        create_file(catchall_path, core["catch-all"], created)
        create_file(site_path, render_site(choice, host, backend_port, root), created)
        if default_target is not None:
            default_link.unlink()
            default_disabled = True
        for name in (catchall_path.name, site_name):
            link = enabled / name
            link.symlink_to(Path("../sites-available") / name)
            created.append(link)
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
    except (OSError, subprocess.CalledProcessError, KeyboardInterrupt):
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if default_disabled:
            default_link.symlink_to(default_target)
        subprocess.run(["nginx", "-t"], check=False)
        subprocess.run(["systemctl", "reload", "nginx"], check=False)
        raise

    print(f"Enabled {host}. Keep a copy of {site_path} in its project repository.")
    print("Check the app or document root, then point DNS to this VPS before requesting TLS.")
    if request_tls:
        try:
            subprocess.run(["certbot", "--nginx", "-d", host, "--redirect"], check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"The HTTP site remains active, but Certbot failed: {error}", file=sys.stderr)
            return 1
        print(f"Copy the Certbot-updated {site_path} to the project repository.")
    return 0


def selected_blueprint(value: str) -> str:
    if value.isascii() and value.isdecimal() and len(value) == 1 and 1 <= int(value) <= len(BLUEPRINTS):
        return list(BLUEPRINTS)[int(value) - 1]
    if value in BLUEPRINTS:
        return value
    raise argparse.ArgumentTypeError("choose a listed number or blueprint name")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="list available blueprints")
    subcommands.add_parser("init", help="interactively install the first gateway site")
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
            return init()
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled.", file=sys.stderr)
            return 1
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"First-run setup failed: {error}", file=sys.stderr)
            return 1

    example_host, example_port, example_root = BLUEPRINTS[args.blueprint]
    if example_port is not None and (args.port is None or args.root is not None):
        parser.error("this blueprint requires --port and does not accept --root")
    if example_root is not None and (args.root is None or args.port is not None):
        parser.error("this blueprint requires --root and does not accept --port")

    result = render_site(args.blueprint, args.host, args.port, args.root)

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
