"""
Regression tests for the feature -> user-doc coverage gap report.

Runs ``scripts/check_doc_feature_coverage.py`` (subprocess smoke) and unit-tests
its label-normalization and coverage helpers.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_doc_feature_coverage.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_doc_feature_coverage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFeatureCoverageScript(unittest.TestCase):
    def test_report_runs_and_is_non_blocking(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"Missing coverage checker: {SCRIPT}")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(REPO_ROOT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "check_doc_feature_coverage.py failed:\n"
                + (proc.stderr or proc.stdout or "(no output)")
            )
        self.assertIn("Doc feature-coverage report:", proc.stdout)
        self.assertIn("unique action labels:", proc.stdout)
        self.assertIn("coverage:", proc.stdout)


class TestNormalizeActionLabel(unittest.TestCase):
    def test_resolves_mnemonics_and_ellipsis(self) -> None:
        module = _load_module()
        cases = {
            "&Open File(s)...": "Open File(s)",
            "Open &Study Index…": "Open Study Index",
            "De-identify && Export DICOM (PS3.15)…": "De-identify & Export DICOM (PS3.15)",
            "E&xit": "Exit",
            "&1×1": "1×1",
        }
        for raw, expected in cases.items():
            self.assertEqual(module.normalize_action_label(raw), expected)


class TestBuildCoverageReport(unittest.TestCase):
    def test_classifies_covered_and_uncovered(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "gui"
            src.mkdir(parents=True)
            (src / "menu.py").write_text(
                'a = QAction("&Export...", w)\n'
                'b = QAction("Secret Debug Mode", w)\n',
                encoding="utf-8",
            )
            docs = root / "user-docs"
            docs.mkdir()
            (docs / "guide.md").write_text(
                "Use **Export** to save your images.\n", encoding="utf-8"
            )
            report, fraction = module.build_coverage_report(root)
        text = "\n".join(report)
        self.assertIn("unique action labels: 2", text)
        self.assertIn("mentioned in user-docs: 1", text)
        self.assertIn('"Secret Debug Mode"', text)
        self.assertNotIn('- "Export"', text)  # covered -> not in candidate-gap list
        self.assertAlmostEqual(fraction, 0.5)


if __name__ == "__main__":
    unittest.main()
