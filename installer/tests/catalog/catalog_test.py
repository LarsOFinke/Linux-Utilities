#!/usr/bin/env python3
"""Check that split manifest validators preserve catalog rejection rules."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from catalog import MODULES, REPOSITORY, installed_components
from catalog import manifest as manifest_reader


def expect_invalid(module: str, source: dict, expected: str, root: Path) -> None:
    (root / "module.json").write_text(json.dumps(source), encoding="utf-8")
    with patch.object(manifest_reader, "REPOSITORY", root):
        try:
            manifest_reader.load_manifest(module, Path("module.json"))
        except SystemExit as error:
            assert expected in str(error), str(error)
        else:
            raise AssertionError(f"Expected invalid {expected}")


def main() -> None:
    manifest = REPOSITORY / MODULES["system"]["manifest"]
    original = json.loads(manifest.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "module.json").write_text(json.dumps(original), encoding="utf-8")
        with patch.object(manifest_reader, "REPOSITORY", root):
            result = manifest_reader.load_manifest("system", Path("module.json"))
        assert result["components"].keys() == original["components"].keys()
        assert result["commands"].keys() == original["commands"].keys()

        old_commands = set(result["commands"]) - {
            "h848_wireplumber_05.conf", "h848_wireplumber_04.lua", "h848_audio_guard.service"
        }
        old_entry = {"components": ["amd-gaming", "h848-audio"],
                     "commands": {name: {} for name in old_commands}}
        assert installed_components("system", old_entry) == {"amd-gaming", "h848-audio"}
        old_entry["commands"].pop("install-h848-audio-fix")
        try:
            installed_components("system", old_entry)
        except RuntimeError as error:
            assert "Inconsistent component registry" in str(error)
        else:
            raise AssertionError("Unexpected missing commands were accepted")

        invalid = copy.deepcopy(original)
        invalid["commands"]["bad name"] = "setup.sh"
        expect_invalid("system", invalid, "Invalid command name", root)

        invalid = copy.deepcopy(original)
        invalid["components"]["amd-gaming"]["commands"].append("install-h848-audio-fix")
        expect_invalid("system", invalid, "Commands shared by system components", root)

        invalid = copy.deepcopy(original)
        invalid["pre_remove"] = {"command": "missing", "args": []}
        expect_invalid("system", invalid, "components must partition", root)

        invalid = copy.deepcopy(original)
        invalid["runtime_configs"] = {"user": ["../escape"]}
        expect_invalid("system", invalid, "Invalid system.runtime_configs.user", root)

        backup = json.loads((REPOSITORY / MODULES["backup"]["manifest"]).read_text(encoding="utf-8"))
        backup["pre_remove"] = {"command": "missing", "args": []}
        expect_invalid("backup", backup, "Invalid backup.pre_remove", root)
    print("Catalog validation tests passed")


if __name__ == "__main__":
    main()
