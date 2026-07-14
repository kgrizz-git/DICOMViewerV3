"""
Regression tests for the incremental architecture boundary checker.

The checker should be usable on a temporary source tree so rules can be
validated without depending on the full application import graph.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_architecture_boundaries.py"


class TestArchitectureBoundaries(unittest.TestCase):
    def test_detects_core_importing_gui(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"Missing architecture checker: {SCRIPT}")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            (src / "core").mkdir(parents=True)
            (src / "gui").mkdir(parents=True)
            (src / "core" / "bad.py").write_text(
                "from gui.main_window import MainWindow\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root)],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("core/bad.py", proc.stderr.replace("\\", "/"))
        self.assertIn("core modules must not import gui", proc.stderr)

    def test_allows_gui_importing_core(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"Missing architecture checker: {SCRIPT}")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            (src / "core").mkdir(parents=True)
            (src / "gui").mkdir(parents=True)
            (src / "gui" / "ok.py").write_text(
                "from core.dicom_parser import get_all_tags\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root)],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
            )

        if proc.returncode != 0:
            self.fail(proc.stderr or proc.stdout or "architecture checker failed")

    def test_baseline_allows_known_violations(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"Missing architecture checker: {SCRIPT}")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            (src / "core").mkdir(parents=True)
            (src / "gui").mkdir(parents=True)
            (src / "core" / "legacy.py").write_text(
                "from gui.main_window import MainWindow\n",
                encoding="utf-8",
            )
            baseline = root / "baseline.txt"
            baseline.write_text(
                "src/core/legacy.py:1: core modules must not import gui; "
                "move UI work to gui or a facade (gui.main_window)\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(root),
                    "--baseline",
                    str(baseline),
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
            )

        if proc.returncode != 0:
            self.fail(proc.stderr or proc.stdout or "baseline did not suppress known violation")


if __name__ == "__main__":
    unittest.main()
