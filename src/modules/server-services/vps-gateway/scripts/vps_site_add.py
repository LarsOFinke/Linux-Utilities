"""Interactively add one site to an initialized gateway."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from vps_site_init import (
    IMPORT_CHOICE,
    ask,
    ask_site_source,
    create_file,
    selected_blueprint,
    site_contents,
    validate_site_contents,
)
from vps_site_model import BLUEPRINTS, document_root, hostname
from vps_site_ports import acknowledge_backend_port, ask_backend_port, configured_ports


def gateway_directories() -> tuple[Path, Path]:
    install_root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
    if install_root == Path("/") and os.geteuid() != 0:
        raise RuntimeError("run site installation with sudo")

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
    return available, enabled


def check_hostname(enabled: Path, host: str, except_link: Path | None = None) -> None:
    for existing in enabled.iterdir():
        if existing == except_link or not existing.is_file():
            continue
        content = existing.read_text(encoding="utf-8")
        for directive in re.findall(r"\bserver_name\s+([^;]+);", content):
            if host in directive.lower().split():
                raise RuntimeError(f"hostname is already configured in {existing}")


def replace_file(path: Path, contents: bytes, mode: int) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".vps-gateway-", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_backup(host: str, contents: bytes) -> Path:
    install_root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
    directory = install_root / "var/lib/shell-scripts/vps-gateway/backups"
    if directory.is_symlink():
        raise RuntimeError(f"refusing symbolic-link backup directory: {directory}")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if directory.stat().st_mode & 0o077:
        raise RuntimeError(f"backup directory is not private: {directory}")
    descriptor, name = tempfile.mkstemp(prefix=f"{host}.", suffix=".conf", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


def deploy_site(available: Path, enabled: Path, host: str, contents: str | bytes,
                replace: bool = False) -> bool:
    site_name = f"{host}.conf"
    site_path = available / site_name
    link = enabled / site_name
    expected_link = Path("../sites-available") / site_name
    site_exists = site_path.exists() or site_path.is_symlink()
    link_exists = link.exists() or link.is_symlink()
    check_hostname(enabled, host, link if link_exists else None)
    data = contents.encode("utf-8") if isinstance(contents, str) else contents
    original = None
    if site_exists or link_exists:
        if (not site_path.is_file() or site_path.is_symlink()
                or not link.is_symlink() or link.readlink() != expected_link):
            raise RuntimeError(f"site paths are not a managed pair: {host}")
        original = site_path.read_bytes()
        if original == data:
            print(f"Site already active and unchanged: {host}")
            return False
        if not replace:
            raise RuntimeError(f"site already exists: {host}; use --replace to update it")

    created: list[Path] = []
    original_mode = site_path.stat().st_mode & 0o777 if original is not None else None
    backup = save_backup(host, original) if original is not None else None
    try:
        if original is None:
            create_file(site_path, contents, created)
            link.symlink_to(expected_link)
            created.append(link)
        else:
            replace_file(site_path, data, original_mode)
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
    except (OSError, subprocess.CalledProcessError, KeyboardInterrupt):
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if original is not None:
            replace_file(site_path, original, original_mode)
        if subprocess.run(["nginx", "-t"], check=False).returncode == 0:
            subprocess.run(["systemctl", "reload", "nginx"], check=False)
        raise
    print(f"{'Updated' if original is not None else 'Enabled'} {host}: {site_path}")
    if backup is not None:
        print(f"Previous site config saved at {backup}")
    return True


def import_site(host: str, contents: bytes, replace: bool = False) -> int:
    available, enabled = gateway_directories()
    validate_site_contents(host, contents)
    deploy_site(available, enabled, host, contents, replace)
    return 0


def add(site_templates: dict[str, str]) -> int:
    available, enabled = gateway_directories()

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
    check_hostname(enabled, host)

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

    if backend_port is not None and backend_port in configured_ports(available):
        raise RuntimeError(f"port {backend_port} was claimed by another gateway site; retry with another port")
    deploy_site(available, enabled, host, contents)

    print(f"Keep a copy of {site_path} in its project repository.")
    if request_tls:
        try:
            subprocess.run(["certbot", "--nginx", "-d", host, "--redirect"], check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"The HTTP site remains active, but Certbot failed: {error}", file=sys.stderr)
            return 1
        print(f"Copy the Certbot-updated {site_path} to the project repository.")
    return 0
