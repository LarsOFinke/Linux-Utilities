#!/usr/bin/env python3
"""Copy the canonical standalone installer into every self-contained module."""

from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "portable_module.py"
MODULES = ("backup", "network", "system", "privacy", "ubuntu-updates", "canary", "vps-gateway")


def main() -> None:
    content = SOURCE.read_bytes()
    for name in MODULES:
        target = SOURCE.parent.parent / name / "portable_module.py"
        target.write_bytes(content)
        print(target.relative_to(SOURCE.parents[2]))


if __name__ == "__main__":
    main()
