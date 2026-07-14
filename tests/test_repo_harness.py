"""
Regression tests for repository harness documentation checks.

Runs ``scripts/check_repo_harness.py`` so CI and local pytest stay aligned.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_repo_harness.py"


def _load_harness_module():
    spec = importlib.util.spec_from_file_location("check_repo_harness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRepoHarness(unittest.TestCase):
    def test_repo_harness_checks_pass(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"Missing harness checker: {SCRIPT}")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(REPO_ROOT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "check_repo_harness.py failed:\n"
                + (proc.stderr or proc.stdout or "(no output)")
            )

    def test_doc_garden_report_mode_is_non_blocking(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"Missing harness checker: {SCRIPT}")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(REPO_ROOT), "--doc-garden"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "check_repo_harness.py --doc-garden failed:\n"
                + (proc.stderr or proc.stdout or "(no output)")
            )
        self.assertIn("Doc garden report:", proc.stdout)
        self.assertIn("harness markdown files", proc.stdout)
        self.assertIn("user guides missing Last updated", proc.stdout)
        self.assertIn("user guides stale", proc.stdout)


class TestScanDocDates(unittest.TestCase):
    """Unit-test the user-guide staleness scan helper."""

    def test_classifies_missing_fresh_and_stale(self) -> None:
        import tempfile

        module = _load_harness_module()
        today = date.today()
        stale_day = (today - timedelta(days=module.DOC_GARDEN_STALE_DAYS + 1)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fresh.md").write_text(
                f"# Fresh\n\n**Last updated:** {today.isoformat()}\n", encoding="utf-8"
            )
            (root / "stale.md").write_text(
                f"# Stale\n\n**Last updated:** {stale_day}\n", encoding="utf-8"
            )
            (root / "nodate.md").write_text("# No date\n\nbody\n", encoding="utf-8")
            missing, stale = module.scan_doc_dates(
                [root / "fresh.md", root / "stale.md", root / "nodate.md"], root, today
            )
        self.assertEqual(missing, ["nodate.md"])
        self.assertEqual(len(stale), 1)
        self.assertIn("stale.md", stale[0])


class TestTodoBacklogPolicy(unittest.TestCase):
    """Unit-test the active-backlog-only TO_DO policy."""

    def test_rejects_changes_history_and_completed_rows(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dev_docs = root / "dev-docs"
            dev_docs.mkdir()
            (dev_docs / "TO_DO.md").write_text(
                "# To-Do Checklist\n\n"
                "**Last updated:** 2026-07-11\n"
                "**Changes:** Old history entry.\n\n"
                "- [ ] Active task\n"
                "- [x] Completed task\n",
                encoding="utf-8",
            )

            errors = module.check_todo_backlog_policy(root)

        self.assertEqual(len(errors), 2)
        self.assertTrue(any("**Changes:**" in error for error in errors))
        self.assertTrue(any("remove completed task row" in error for error in errors))

    def test_accepts_active_backlog_only(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dev_docs = root / "dev-docs"
            dev_docs.mkdir()
            (dev_docs / "TO_DO.md").write_text(
                "# To-Do Checklist\n\n"
                "**Last updated:** 2026-07-11\n\n"
                "- [ ] Active task\n",
                encoding="utf-8",
            )

            errors = module.check_todo_backlog_policy(root)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
