"""Require the requested System utility component to be registered."""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    binary = Path(os.environ["LINUX_UTILITIES_BUNDLE_PATH"]).resolve()
    if binary.parent == Path.home() / ".local/bin":
        home = Path.home()
        states = (home / ".local/state/shell-scripts/registry.json",
                  home / ".local/state/shell-scripts/portable/system.json")
    else:
        root = binary.parents[3]
        states = (root / "var/lib/shell-scripts/registry.json",
                  root / "var/lib/shell-scripts/portable/system.json")
    for path in states:
        if path.is_symlink() or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entry = data.get("modules", {}).get("system") if "modules" in data else data
            if entry and Path(entry["commands"]["system-utils"]["path"]) == binary:
                return 0 if sys.argv[1] in entry.get("components", []) else 1
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return 1


if __name__ == "__main__":
    sys.exit(main())
