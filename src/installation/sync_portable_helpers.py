#!/usr/bin/env python3
"""Copy the canonical standalone installer into every self-contained module."""

import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "portable_module.py"
REPOSITORY = SOURCE.parents[2]


def main() -> None:
    content = SOURCE.read_bytes()
    catalog = json.loads((REPOSITORY / "configuration/install.json").read_text(encoding="utf-8"))
    for manifest in catalog["modules"].values():
        target = (REPOSITORY / manifest).parent / "portable_module.py"
        target.write_bytes(content)
        print(target.relative_to(REPOSITORY))


if __name__ == "__main__":
    main()
