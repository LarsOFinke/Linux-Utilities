"""Report portable installation state and changed commands on an SSH target."""

import hashlib
import json
import os
import pathlib
import sys

system = sys.argv[1] == "system"
base = pathlib.Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve() if system else pathlib.Path.home()
directory = base / ("var/lib/shell-scripts/portable" if system else ".local/state/shell-scripts/portable")
result = {}
for path in directory.glob("*.json"):
    if path.is_symlink():
        continue
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("id") != path.stem or state.get("system") != system:
            continue
        issues = []
        for name, record in state.get("commands", {}).items():
            command = pathlib.Path(record["path"])
            if command.is_symlink() or not command.is_file():
                issues.append("missing command " + name)
            elif hashlib.sha256(command.read_bytes()).hexdigest() != record["sha256"]:
                issues.append("modified command " + name)
        result[path.stem] = {"components": state.get("components"), "issues": issues}
    except (OSError, ValueError, KeyError, TypeError):
        result[path.stem] = {"components": None, "issues": ["invalid remote portable state"]}
print(json.dumps(result))
