"""Interactively add one site to an initialized gateway."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from vps_site_init import (
    IMPORT_CHOICE,
    ask,
    ask_site_source,
    create_file,
    selected_blueprint,
    site_contents,
)
from vps_site_model import BLUEPRINTS, document_root, hostname
from vps_site_ports import acknowledge_backend_port, ask_backend_port, configured_ports


def add(site_templates: dict[str, str]) -> int:
    install_root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
    if install_root == Path("/") and os.geteuid() != 0:
        raise RuntimeError("run the site wizard with sudo")

    nginx_dir = install_root / "etc/nginx"
    available = nginx_dir / "sites-available"
    enabled = nginx_dir / "sites-enabled"
    catchall = enabled / "vps-gateway-catch-all.conf"
    expected_catchall = Path("../sites-available/vps-gateway-catch-all.conf")
    if not (nginx_dir / "conf.d/vps-gateway.conf").is_file() or not (
        nginx_dir / "snippets/vps-gateway-proxy-headers.conf"
    ).is_file() or not catchall.is_symlink() or catchall.readlink() != expected_catchall or not catchall.is_file():
        raise RuntimeError("gateway core or catch-all is missing; initialize the gateway first")
    if not available.is_dir() or not enabled.is_dir():
        raise RuntimeError("NGINX site directories are missing")

    print("Add a VPS gateway site")
    for number, name in enumerate(BLUEPRINTS, 1):
        print(f"  {number}. {name}")
    print(f"  {len(BLUEPRINTS) + 1}. {IMPORT_CHOICE} (copy a project site config)")
    choice = ask("Site option number", selected_blueprint)
    host = ask("Public DNS hostname", hostname)
    source = ask_site_source() if choice == IMPORT_CHOICE else None
    backend_port = (
        ask_backend_port(available)
        if choice != IMPORT_CHOICE and BLUEPRINTS[choice][1] is not None
        else None
    )
    root = (
        ask("Absolute document root", document_root)
        if choice != IMPORT_CHOICE and backend_port is None
        else None
    )
    contents = site_contents(choice, host, backend_port, root, site_templates, source)
    site_name = f"{host}.conf"
    site_path = available / site_name
    link = enabled / site_name
    if site_path.exists() or site_path.is_symlink() or link.exists() or link.is_symlink():
        raise RuntimeError(f"site already exists: {host}")

    # A differently named enabled file may already claim the same exact host.
    for existing in enabled.iterdir():
        if not existing.is_file():
            continue
        content = existing.read_text(encoding="utf-8")
        for directive in re.findall(r"\bserver_name\s+([^;]+);", content):
            if host in directive.split():
                raise RuntimeError(f"hostname is already configured in {existing}")

    print(f"\nWill activate {host} from {choice}.")
    print(f"Site: {site_path}")
    print(f"Enabled link: {link}")
    if source is not None:
        print(f"Copy unchanged from: {source}")
    if backend_port is not None and not acknowledge_backend_port(backend_port):
        print("No changes made.")
        return 0
    request_tls = input("Request a TLS certificate after activation? DNS must already point here. [y/N] ").strip().lower() == "y"
    if input("Add this site? [y/N] ").strip().lower() != "y":
        print("No changes made.")
        return 0

    created: list[Path] = []
    try:
        if backend_port is not None and backend_port in configured_ports(available):
            raise RuntimeError(f"port {backend_port} was claimed by another gateway site; retry with another port")
        create_file(site_path, contents, created)
        link.symlink_to(Path("../sites-available") / site_name)
        created.append(link)
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
    except (OSError, subprocess.CalledProcessError, KeyboardInterrupt):
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if subprocess.run(["nginx", "-t"], check=False).returncode == 0:
            subprocess.run(["systemctl", "reload", "nginx"], check=False)
        raise

    print(f"Enabled {host}. Keep a copy of {site_path} in its project repository.")
    if request_tls:
        try:
            subprocess.run(["certbot", "--nginx", "-d", host, "--redirect"], check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"The HTTP site remains active, but Certbot failed: {error}", file=sys.stderr)
            return 1
        print(f"Copy the Certbot-updated {site_path} to the project repository.")
    return 0
