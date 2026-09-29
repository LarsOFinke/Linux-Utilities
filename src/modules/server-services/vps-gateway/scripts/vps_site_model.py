"""Blueprint metadata, validation, and site rendering."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

BLUEPRINTS = {
    "http-app": ("app.example.org", "18081", None),
    "java-spring": ("java.example.org", "18083", None),
    "python-asgi": ("python.example.org", "18084", None),
    "websocket": ("socket.example.org", "18082", None),
    "static-html": ("static.example.org", None, "/srv/www/static.example.org"),
    "spa": ("spa.example.org", None, "/srv/www/spa.example.org"),
}


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


def render_site(site_templates: dict[str, str], blueprint: str, host: str, backend_port: int | None, root: str | None) -> str:
    example_host, example_port, example_root = BLUEPRINTS[blueprint]
    result = site_templates[blueprint]
    if example_port is not None:
        if backend_port is None or root is not None:
            raise ValueError("this blueprint requires a port")
        result = result.replace(f"127.0.0.1:{example_port}", f"127.0.0.1:{backend_port}")
    else:
        if root is None or backend_port is not None:
            raise ValueError("this blueprint requires a document root")
        result = result.replace(example_root, root)
    return result.replace(example_host, host)
