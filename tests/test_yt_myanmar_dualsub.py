"""Python unittest bridge executing the Node.js unit test suite for Loon scripts."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class YouTubeMyanmarDualSubTests(unittest.TestCase):
    def test_node_unit_suite_passes(self) -> None:
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required to run JS unit tests")
        js_tests = [str(p.relative_to(ROOT)) for p in sorted((ROOT / "tests" / "js").glob("*.test.mjs"))]
        self.assertTrue(js_tests, "Expected at least one *.test.mjs file under tests/js/")
        res = subprocess.run(
            [node, "--test", *js_tests],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Node tests failed (rc={res.returncode}):\n{res.stdout}\n{res.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
