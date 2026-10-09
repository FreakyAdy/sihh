import json
import subprocess
import sys
import unittest
from pathlib import Path


class ReleaseCheckTests(unittest.TestCase):
    def test_release_check_passes_and_emits_benchmark(self) -> None:
        root = Path(__file__).parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "release_check.py")],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertTrue(payload["benchmark"]["passed"])
        self.assertIn("docs/demo-runbook.md", payload["required_paths"])


if __name__ == "__main__":
    unittest.main()
