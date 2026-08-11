"""
Regression test for user-docs (and dev-docs README) relative Markdown links.

Runs ``scripts/check_user_docs_links.py`` so CI and local pytest stay aligned.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
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


class TestUserDocsDevDocsBoundary(unittest.TestCase):
    """user-docs/ must not link into dev-docs/plans/ or dev-docs/TO_DO.md.
    Links into dev-docs/info/ and other dev-docs/ root files are allowed."""

    def _run_on_tree(self, tree_root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(tree_root)],
            cwd=str(tree_root),
            capture_output=True,
            text=True,
            check=False,
        )

    def _make_repo(self, tmp: Path) -> tuple[Path, Path]:
        (tmp / "user-docs").mkdir()
        (tmp / "dev-docs" / "plans").mkdir(parents=True)
        (tmp / "dev-docs" / "info").mkdir(parents=True)
        (tmp / "dev-docs" / "plans" / "SOME_PLAN.md").write_text("# plan\n")
        (tmp / "dev-docs" / "info" / "SOME_INFO.md").write_text("# info\n")
        (tmp / "dev-docs" / "TO_DO.md").write_text("# to-do\n")
        (tmp / "dev-docs" / "RELEASING.md").write_text("# releasing\n")
        return tmp / "user-docs", tmp / "dev-docs"

    def test_user_doc_link_into_dev_docs_plans_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, _ = self._make_repo(tmp)
            (user_docs / "guide.md").write_text(
                "See [plan](../dev-docs/plans/SOME_PLAN.md).\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("user-docs must not link into dev-docs/plans", proc.stderr)

    def test_user_doc_link_into_dev_docs_info_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, _ = self._make_repo(tmp)
            (user_docs / "guide.md").write_text(
                "See [info](../dev-docs/info/SOME_INFO.md).\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_user_doc_link_into_dev_docs_todo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, _ = self._make_repo(tmp)
            (user_docs / "guide.md").write_text(
                "See [todo](../dev-docs/TO_DO.md).\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("user-docs must not link into dev-docs/TO_DO.md", proc.stderr)

    def test_user_doc_link_into_dev_docs_root_other_than_todo_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, _ = self._make_repo(tmp)
            (user_docs / "guide.md").write_text(
                "See [releasing](../dev-docs/RELEASING.md).\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_user_doc_link_to_dev_docs_directory_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, _ = self._make_repo(tmp)
            (user_docs / "guide.md").write_text(
                "See [dev-docs](../dev-docs/).\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertNotEqual(proc.returncode, 139, "script crashed")
            self.assertNotIn("IndexError", proc.stderr)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_user_doc_link_to_another_user_doc_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, _ = self._make_repo(tmp)
            (user_docs / "other.md").write_text("# other\n")
            (user_docs / "guide.md").write_text("See [other](other.md).\n")
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_dev_docs_readme_link_into_dev_docs_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, dev_docs = self._make_repo(tmp)
            (dev_docs / "README.md").write_text(
                "Plan index: [plan](plans/SOME_PLAN.md).\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
