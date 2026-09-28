import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tools" / "canary_project" / "__main__.py"


class CanaryProjectTest(unittest.TestCase):
    def test_generates_project_with_common_targets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = pathlib.Path(temp_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.canary_project",
                    "--project-name",
                    "demo-site",
                    "--output-dir",
                    str(output_dir),
                    "--mode",
                    "standard",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            project_dir = output_dir / "demo-site"
            self.assertTrue(project_dir.exists())
            for relative_path in [
                "api/.env",
                "api/health",
                "config/app.env",
                "public/index.php",
                "server.py",
                "README.md",
                "tos.md",
            ]:
                self.assertTrue((project_dir / relative_path).exists(), relative_path)

            readme = (project_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("demo-site", readme)
            self.assertIn("/api/.env", readme)


if __name__ == "__main__":
    unittest.main()
