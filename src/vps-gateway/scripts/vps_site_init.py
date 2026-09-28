"""Interactive first-run deployment with validation and rollback."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from vps_site_model import BLUEPRINTS, document_root, hostname, render_site
from vps_site_ports import acknowledge_backend_port, ask_backend_port

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


def init(site_templates: dict[str, str], core: dict[str, str]) -> int:
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
        backend_port = ask_backend_port(install_root / "etc/nginx/sites-available")
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
    if backend_port is not None and not acknowledge_backend_port(backend_port):
        print("No changes made.")
        return 0
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
        create_file(core_path, core["http"], created)
        create_file(headers_path, core["proxy-headers"], created)
        create_file(catchall_path, core["catch-all"], created)
        create_file(site_path, render_site(site_templates, choice, host, backend_port, root), created)
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
