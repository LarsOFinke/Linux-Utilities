#!/usr/bin/env python3
"""Focused behavior checks for loc-rank."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


COMMAND = Path(__file__).resolve().parents[1] / "scripts/loc-rank"


class LocRankTest(unittest.TestCase):
    def test_source_selection_line_counts_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.py").write_text("one\n\nthree", encoding="utf-8")
            (root / "b.vue").write_text("one\ntwo\nthree\n", encoding="utf-8")
            (root / "c.cpp").write_text("one\ntwo\n", encoding="utf-8")
            (root / "d.py").write_text("one", encoding="utf-8")
            (root / "notes.md").write_text("one\n" * 9, encoding="utf-8")
            (root / "binary.ts").write_bytes(b"one\0two\n")
            (root / "tool").write_text("#!/usr/bin/env python3\nprint('hi')\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "large.py").write_text("x\n" * 20, encoding="utf-8")
            (root / ".hidden").mkdir()
            (root / ".hidden" / "large.py").write_text("x\n" * 20, encoding="utf-8")
            (root / "link.py").symlink_to(root / "a.py")
            (root / "linked_directory").symlink_to(root / "node_modules", target_is_directory=True)

            result = subprocess.run([sys.executable, str(COMMAND), str(root)],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.splitlines(), [
                "[.cpp]", "LINES  FILE", "    2  c.cpp", "",
                "[script (python)]", "LINES  FILE", "    2  tool", "",
                "[.py]", "LINES  FILE", "    1  d.py", "    3  a.py", "",
                "[.vue]", "LINES  FILE", "    3  b.vue",
            ])

            limited = subprocess.run([sys.executable, str(COMMAND), "--top", "3", str(root)],
                                     capture_output=True, text=True, check=True)
            self.assertEqual(limited.stdout.splitlines(), [
                "[.cpp]", "LINES  FILE", "    2  c.cpp", "",
                "[.py]", "LINES  FILE", "    3  a.py", "",
                "[.vue]", "LINES  FILE", "    3  b.vue",
            ])

    def test_invalid_directory_and_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for args in ((str(Path(temporary) / "missing"),), ("--top", "0", temporary)):
                result = subprocess.run([sys.executable, str(COMMAND), *args],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
