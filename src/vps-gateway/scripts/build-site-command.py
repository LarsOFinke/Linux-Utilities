#!/usr/bin/env python3
"""Embed blueprint examples in the installed standalone site generator."""

from __future__ import annotations

import ast
import os
import pprint
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build-site-command.py OUTPUT")
    module = Path(__file__).resolve().parents[1]
    source = (module / "scripts/vps-gateway-site.py").read_text(encoding="utf-8")
    marker = "\nTEMPLATES = None\n"
    core_marker = "\nCORE_TEMPLATES = None\n"
    if source.count(marker) != 1:
        raise SystemExit("site generator template marker is missing or repeated")
    if source.count(core_marker) != 1:
        raise SystemExit("core template marker is missing or repeated")
    definition = next(
        (node.value for node in ast.parse(source).body
         if isinstance(node, ast.Assign)
         and any(isinstance(target, ast.Name) and target.id == "BLUEPRINTS" for target in node.targets)),
        None,
    )
    if definition is None:
        raise SystemExit("site generator blueprint list is missing")
    blueprint_names = ast.literal_eval(definition)
    contents = {name: (module / "configuration/blueprints" / f"{name}.conf.example").read_text(encoding="utf-8")
                for name in blueprint_names}
    core_contents = {name: (module / "configuration/core" / f"{name}.conf.example").read_text(encoding="utf-8")
                     for name in ("http", "proxy-headers", "catch-all")}
    output = Path(sys.argv[1])
    output.write_text(
        source.replace(marker, "\nTEMPLATES = " + pprint.pformat(contents, width=100) + "\n")
        .replace(core_marker, "\nCORE_TEMPLATES = " + pprint.pformat(core_contents, width=100) + "\n"),
        encoding="utf-8",
    )
    os.chmod(output, 0o755)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
