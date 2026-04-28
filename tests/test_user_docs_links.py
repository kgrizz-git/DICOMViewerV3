"""
Regression test for user-docs (and dev-docs README) relative Markdown links.

Runs ``scripts/check_user_docs_links.py`` so CI and local pytest stay aligned.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_user_docs_links.py"


class TestUserDocsRelativeLinks(unittest.TestCase):
    def test_user_docs_relative_links_resolve(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"Missing link checker script: {SCRIPT}")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(REPO_ROOT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "check_user_docs_links.py failed:\n"
                + (proc.stderr or proc.stdout or "(no output)")
            )


if __name__ == "__main__":
    unittest.main()
