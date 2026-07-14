"""
Regression tests for agent smoke harness script (no full GUI).

Runs ``scripts/agent_smoke_harness.py`` without --qt-smoke for CI compatibility.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "agent_smoke_harness.py"


class TestAgentSmokeHarness(unittest.TestCase):
    def test_agent_smoke_harness_passes_without_gui(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"Missing agent smoke script: {SCRIPT}")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(REPO_ROOT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "agent_smoke_harness.py failed:\n"
                + (proc.stderr or proc.stdout or "(no output)")
            )


if __name__ == "__main__":
    unittest.main()
