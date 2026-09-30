"""Interactive first-run deployment with validation and rollback."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from vps_site_model import BLUEPRINTS, document_root, hostname, render_site
from vps_site_ports import acknowledge_backend_port, ask_backend_port

IMPORT_CHOICE = "import-existing"
CORE_ONLY_CHOICE = "core-only"


def ask(label: str, validator) -> str | int:
    while True:
        value = input(f"{label}: ").strip()
        try:
            return validator(value)
        except argparse.ArgumentTypeError as error:
            print(f"Invalid value: {error}", file=sys.stderr)


def create_file(path: Path, contents: str | bytes, created: list[Path]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    created.append(path)
    if isinstance(contents, bytes):
        stream = os.fdopen(descriptor, "wb")
    else:
        stream = os.fdopen(descriptor, "w", encoding="utf-8")
    with stream:
        stream.write(contents)


def validate_site_contents(host: str, contents: bytes) -> None:
    text = contents.decode("utf-8")
    active_lines = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    names = re.findall(r"\bserver_name\s+([^;]+);", active_lines)
    if not any(host in declared.lower().split() for declared in names):
        raise RuntimeError(f"site config does not declare server_name {host}")


def site_contents(choice: str, host: str, backend_port: int | None, root: str | None,
                  site_templates: dict[str, str], source: Path | None) -> str | bytes:
    if source is None:
        return render_site(site_templates, choice, host, backend_port, root)
    if not source.is_absolute() or source.is_symlink() or not source.is_file():
        raise RuntimeError(f"project site config must be an absolute regular file: {source}")
    contents = source.read_bytes()
    validate_site_contents(host, contents)
    return contents


def ask_site_source() -> Path:
    while True:
        value = input("Absolute path to the project's NGINX site config: ").strip()
        source = Path(value)
        if source.is_absolute() and source.is_file() and not source.is_symlink():
            return source
        print("Enter an absolute path to a regular config file (not a symlink).", file=sys.stderr)


def require_distribution_includes(nginx_conf: Path) -> None:
    contents = nginx_conf.read_text(encoding="utf-8")
    for pattern, label in (
        (r"^\s*include\s+/etc/nginx/conf\.d/\*\.conf\s*;", "conf.d/*.conf"),
        (r"^\s*include\s+/etc/nginx/sites-enabled/\*\s*;", "sites-enabled/*"),
    ):
        if not re.search(pattern, contents, re.MULTILINE):
            raise RuntimeError(f"nginx.conf does not include {label}; integrate the gateway manually")


def init(site_templates: dict[str, str], core: dict[str, str], empty: bool = False) -> int:
    install_root = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
    if install_root == Path("/") and os.geteuid() != 0:
        raise RuntimeError("run the first-run wizard with sudo")
    choice = CORE_ONLY_CHOICE if empty else None
    if not empty:
        print("Initialize VPS gateway")
        for number, name in enumerate(BLUEPRINTS, 1):
            print(f"  {number}. {name}")
        print(f"  {len(BLUEPRINTS) + 1}. {IMPORT_CHOICE} (copy a project site config)")
        print(f"  {len(BLUEPRINTS) + 2}. {CORE_ONLY_CHOICE} (let projects import their own sites)")
        choice = ask("Site option number", selected_blueprint)
    host = ask("Public DNS hostname", hostname) if choice != CORE_ONLY_CHOICE else None
    backend_port = None
    root = None
    source = ask_site_source() if choice == IMPORT_CHOICE else None
    if choice in BLUEPRINTS and BLUEPRINTS[choice][1] is not None:
        backend_port = ask_backend_port(install_root / "etc/nginx/sites-available")
    elif choice in BLUEPRINTS:
        root = ask("Absolute document root", document_root)
    contents = site_contents(choice, host, backend_port, root, site_templates, source) if host else None
    site_name = f"{host}.conf" if host else None
    nginx_dir = install_root / "etc/nginx"
    available = nginx_dir / "sites-available"
    enabled = nginx_dir / "sites-enabled"
    site_path = available / site_name if site_name else None
    core_path = nginx_dir / "conf.d/vps-gateway.conf"
    headers_path = nginx_dir / "snippets/vps-gateway-proxy-headers.conf"
    catchall_path = available / "vps-gateway-catch-all.conf"
    default_link = enabled / "default"

    print(f"\nWill install NGINX/Certbot and initialize the gateway{f' for {host}' if host else ' without a site'}.")
    if site_path is not None:
        print(f"Site: {site_path}")
    if source is not None:
        print(f"Copy unchanged from: {source}")
    print(f"Core: {core_path}")
    print("The packaged default site will be disabled and unknown hosts rejected.")
    if backend_port is not None and not acknowledge_backend_port(backend_port):
        print("No changes made.")
        return 0
    request_tls = bool(host) and input("Request a TLS certificate after activation? DNS must already point here. [y/N] ").strip().lower() == "y"
    if not empty and input("Apply this first-run setup? [y/N] ").strip().lower() != "y":
        print("No changes made.")
        return 0

    subprocess.run([str(Path(__file__).with_name("vps-gateway")), "configure"], check=True)
    if not (nginx_dir / "nginx.conf").is_file():
        raise RuntimeError(f"NGINX configuration is missing: {nginx_dir / 'nginx.conf'}")
    require_distribution_includes(nginx_dir / "nginx.conf")
    for directory in (available, enabled, nginx_dir / "conf.d", nginx_dir / "snippets"):
        if not directory.is_dir():
            raise RuntimeError(f"NGINX directory is missing: {directory}")
    other_sites = [path.name for path in enabled.iterdir() if path.name != "default"]
    if other_sites:
        raise RuntimeError(f"first-run setup requires no other enabled sites: {', '.join(other_sites)}")
    other_conf = list((nginx_dir / "conf.d").glob("*.conf"))
    if other_conf:
        raise RuntimeError("first-run setup requires an empty /etc/nginx/conf.d; review existing config manually")
    targets = [core_path, headers_path, catchall_path, enabled / catchall_path.name]
    if site_path is not None:
        targets.extend((site_path, enabled / site_name))
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
        if site_path is not None:
            create_file(site_path, contents, created)
        if default_target is not None:
            default_link.unlink()
            default_disabled = True
        for name in (catchall_path.name, *([site_name] if site_name else [])):
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

    if site_path is None:
        print("Gateway initialized without project sites. Project deployments can now import their routes.")
        return 0
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
    choices = [*BLUEPRINTS, IMPORT_CHOICE, CORE_ONLY_CHOICE]
    if value.isascii() and value.isdecimal() and len(value) == 1 and 1 <= int(value) <= len(choices):
        return choices[int(value) - 1]
    if value in choices:
        return value
    raise argparse.ArgumentTypeError("choose a listed number or site option name")
