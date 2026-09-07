"""
Regression tests for documentation references: relative Markdown links, the
user-docs/dev-docs boundary rules, and inline ``src/...`` code paths.

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
        (tmp / "dev-docs" / "info" / "TO_DO.md").write_text("# nested todo\n")
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

    def test_user_doc_link_into_nested_todo_in_info_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, _ = self._make_repo(tmp)
            (user_docs / "guide.md").write_text(
                "See [nested](../dev-docs/info/TO_DO.md).\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

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

    def test_symlink_in_user_docs_to_dev_docs_plan_is_classified_as_user_doc(self) -> None:
        """A symlink inside user-docs/ pointing to dev-docs/plans/ must still
        be classified as a user-doc so boundary checks apply to its links."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            user_docs, dev_docs = self._make_repo(tmp)
            plan = dev_docs / "plans" / "REAL_PLAN.md"
            plan.write_text("# plan\n")
            link = user_docs / "guide.md"
            link.symlink_to(Path("..") / "dev-docs" / "plans" / "REAL_PLAN.md")
            # Content with a link that resolves into dev-docs/ from user-docs/.
            plan.write_text("See [todo](../dev-docs/TO_DO.md).\n")
            # Without the fix, is_user_doc=False (resolved path is in
            # dev-docs/plans/) and the boundary check is skipped, so the
            # script exits 0 despite the forbidden link content.
            # With the fix, is_user_doc=True (apparent path in user-docs/)
            # and the boundary check rejects the TO_DO.md link.
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("user-docs must not link into dev-docs/TO_DO.md", proc.stderr)

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


class TestInlineSrcCodePaths(unittest.TestCase):
    """A doc naming `src/pkg/module.py` must name one that exists.

    This is the check that a core/ to gui/ package move defeats: the prose stays
    syntactically fine and every Markdown link still resolves, but the module it
    names has moved. Seventeen such references were stale before this existed.
    """

    def _run_on_tree(self, tree_root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(tree_root)],
            cwd=str(tree_root),
            capture_output=True,
            text=True,
            check=False,
        )

    def _make_repo(self, tmp: Path) -> Path:
        (tmp / "user-docs").mkdir()
        (tmp / "dev-docs").mkdir()
        (tmp / "src" / "gui").mkdir(parents=True)
        (tmp / "src" / "gui" / "mpr_controller.py").write_text("")
        return tmp / "dev-docs"

    def test_moved_module_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._make_repo(tmp)
            (dev_docs / "GUIDE.md").write_text(
                "MPR lives in `src/core/mpr_controller.py` today.\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("src/core/mpr_controller.py", proc.stderr)
            self.assertIn("names a source file that does not exist", proc.stderr)

    def test_correct_module_path_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._make_repo(tmp)
            (dev_docs / "GUIDE.md").write_text(
                "MPR lives in `src/gui/mpr_controller.py` today.\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_illustrative_ellipsis_path_is_not_a_claim(self) -> None:
        """`src/...py` is prose, not an assertion that a file exists."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._make_repo(tmp)
            (dev_docs / "GUIDE.md").write_text(
                "The check also validates inline `src/...py` paths.\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_directory_and_glob_mentions_are_not_claims(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._make_repo(tmp)
            (dev_docs / "GUIDE.md").write_text(
                "See `src/gui/` and `src/gui/main_window_*_builder.py` for detail.\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_wrong_case_is_reported_on_any_platform(self) -> None:
        """macOS and Windows resolve paths case-insensitively; Linux CI does not.

        Without an exact-case comparison a mis-cased path passes the pre-commit
        hook on a Mac and then fails the same check on CI.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._make_repo(tmp)
            (dev_docs / "GUIDE.md").write_text(
                "MPR lives in `src/GUI/mpr_controller.py`.\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("src/GUI/mpr_controller.py", proc.stderr)

    def test_plans_directory_is_not_checked(self) -> None:
        """dev-docs/plans/ is historical record; stale paths there are expected."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._make_repo(tmp)
            (dev_docs / "plans").mkdir()
            (dev_docs / "plans" / "OLD_PLAN.md").write_text(
                "Back then it was `src/core/mpr_controller.py`.\n"
            )
            proc = self._run_on_tree(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
