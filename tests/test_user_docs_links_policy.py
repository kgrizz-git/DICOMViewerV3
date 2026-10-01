"""
Policy tests for ``scripts/check_user_docs_links.py``: which documents are in
the blocking set, which inline-path classes are exempt, and how historical
material is handled.

Split out of ``test_user_docs_links.py`` to keep both files under the repo's
750-line source-size threshold. Same checker, same fixtures, invoked the same
way, so CI and local pytest stay aligned.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_user_docs_links.py"


class TestPlanTreePolicy(unittest.TestCase):
    """dev-docs/plans/ is split: active plans are checked, completed ones are not.

    A completed plan describes the tree as it was, so a link to a since-renamed
    file is an accurate record. An *active* plan is a live work document, so a
    broken link in it misleads whoever is implementing it.
    """

    def _run(self, tmp: Path, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(tmp), *extra],
            cwd=str(tmp),
            capture_output=True,
            text=True,
            check=False,
        )

    def _tree(self, tmp: Path) -> Path:
        (tmp / "user-docs").mkdir()
        (tmp / "src" / "core").mkdir(parents=True)
        (tmp / "src" / "core" / "real_module.py").write_text("x = 1\n")
        (tmp / "dev-docs").mkdir()
        (tmp / "dev-docs" / "TO_DO.md").write_text("# to-do\n")
        (tmp / "dev-docs" / "info").mkdir()
        (tmp / "dev-docs" / "plans").mkdir(parents=True)
        (tmp / "dev-docs" / "plans" / "supporting").mkdir()
        (tmp / "dev-docs" / "plans" / "completed").mkdir()
        return tmp / "dev-docs"

    def test_broken_link_in_an_active_plan_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "plans" / "ACTIVE_PLAN.md").write_text(
                "See [todo](../TO_DO_MISSING.md).\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("broken link", proc.stderr)

    def test_broken_link_in_a_supporting_plan_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "plans" / "supporting" / "S.md").write_text(
                "See [nope](../../nowhere.md).\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("broken link", proc.stderr)

    def test_active_plan_cannot_name_a_proposed_module(self) -> None:
        """Plans may name modules they intend to create; that is not link rot.

        The inline ``src/...py`` check asserts a path exists *now*, which is true
        of descriptive docs but false of a plan's "add ``src/core/thing.py``".
        Applying it there reported 17 proposed modules as broken, which no edit
        could ever fix, so a gate would be permanently red.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "plans" / "ACTIVE.md").write_text(
                "Add `src/core/not_created_yet.py` first.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_descriptive_doc_still_rejects_a_stale_module_path(self) -> None:
        """The src/ check is scoped to plans only, not disabled repo-wide."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "ARCHITECTURE.md").write_text(
                "See `src/core/moved_away.py`.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("names a code file", proc.stderr)

    def test_completed_plan_rot_is_advisory_not_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "plans" / "completed" / "DONE.md").write_text(
                "See [gone](../NO_LONGER_THERE.md).\n"
            )
            proc = self._run(tmp, "--include-completed-plans")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Advisory only", proc.stderr)
            self.assertIn("broken link", proc.stderr)

    def test_advisory_mode_actually_covers_the_changelog(self) -> None:
        """The flag documents CHANGELOG.md coverage, so it must scan it.

        ``_is_excluded`` only *demotes* a file; it never introduces one. Without
        an explicit add, the flag claimed coverage of the historical set while
        never passing CHANGELOG.md to the scanner - the same reads-as-configured
        -while-doing-nothing shape the flag is meant to avoid.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / "CHANGELOG.md").write_text(
                "## 1.0.0\n\nSee [gone](dev-docs/NO_SUCH_FILE.md).\n"
            )
            proc = self._run(tmp, "--include-completed-plans")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Advisory only", proc.stderr)
            self.assertIn("CHANGELOG.md", proc.stderr)

    def test_changelog_is_not_scanned_in_blocking_mode(self) -> None:
        """CHANGELOG rot must never block a merge."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / "CHANGELOG.md").write_text(
                "## 1.0.0\n\nSee [gone](dev-docs/NO_SUCH_FILE.md).\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_stale_workflow_reference_in_a_living_doc_is_blocking(self) -> None:
        """A doc naming a workflow inline is asserting the file exists now."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / ".github" / "workflows").mkdir(parents=True)
            (tmp / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")
            (tmp / "dev-docs" / "GUIDE.md").write_text(
                "Runs in `.github/workflows/ci.yml` and "
                "`.github/workflows/grype.yml`.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("grype.yml", proc.stderr)
            self.assertNotIn("ci.yml", proc.stderr)

    def test_stale_workflow_reference_in_an_active_plan_is_blocking(self) -> None:
        """The src/ check is plan-exempt; the workflow check deliberately is not.

        A plan may *propose* a new module, so naming a not-yet-created
        ``src/core/thing.py`` is not rot. A workflow or requirements file is
        never proposed, so this class is safe to enforce in the plan tree — which
        is how three consolidated workflows went stale unnoticed.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (tmp / ".github" / "workflows").mkdir(parents=True)
            (dev_docs / "plans" / "ACTIVE.md").write_text(
                "Job lives in `.github/workflows/security-checks.yml`.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("security-checks.yml", proc.stderr)

    def test_active_plan_may_still_propose_a_module(self) -> None:
        """Guards the boundary the previous test relies on: proposals stay allowed."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (tmp / ".github" / "workflows").mkdir(parents=True)
            (tmp / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")
            (dev_docs / "plans" / "ACTIVE.md").write_text(
                "Add `src/core/not_created.py`; edit `.github/workflows/ci.yml`.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_every_known_repo_path_arm_is_reachable(self) -> None:
        """Every arm of KNOWN_REPO_PATH_PATTERN is exercised, present and absent.

        The `.githooks/` arm shipped dead -- it required a word character before a
        dot-directory, so it could never match -- and it shipped because every
        other arm did match and the tests only ever used a workflow path. One
        assertion per arm, for the existing and the missing case, closes that.
        """
        cases = [
            (".github/workflows/ci.yml", True),
            (".github/workflows/ci.yaml", True),
            ("requirements.txt", True),
            ("requirements-dev.txt", True),
            ("pytest.ini", True),
            ("ruff.toml", True),
            # NB: the set is *closed*, so `pyproject.toml` / `ruff-x.toml` are
            # deliberately NOT arms -- two plans propose a `pyproject.toml`, and
            # flagging it would be the proposal false positive again.
            (".coveragerc", True),
            (".githooks/pre-commit", True),
            (".github/workflows/gone.yml", False),
            ("requirements-imaginary.txt", False),
            (".githooks/imaginary", False),
        ]
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / ".github" / "workflows").mkdir(parents=True)
            (tmp / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")
            (tmp / ".github" / "workflows" / "ci.yaml").write_text("name: CI\n")
            (tmp / ".githooks").mkdir(parents=True)
            (tmp / ".githooks" / "pre-commit").write_text("#!/bin/sh\n")
            for name in ("requirements.txt", "requirements-dev.txt",
                         "pytest.ini", "ruff.toml", ".coveragerc"):
                (tmp / name).write_text("x = 1\n")
            present = [c for c, ok in cases if ok]
            absent = [c for c, ok in cases if not ok]
            (tmp / "dev-docs" / "GUIDE.md").write_text(
                "".join(f"See `{c}`.\n" for c in present)
            )
            self.assertEqual(self._run(tmp).returncode, 0)
            (tmp / "dev-docs" / "GUIDE.md").write_text(
                "".join(f"See `{c}`.\n" for c in absent)
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            for c in absent:
                self.assertIn(c, proc.stderr)

    def test_descriptive_doc_flags_stale_scripts_and_tests_paths(self) -> None:
        """The positive case for the ``scripts``/``tests`` arms.

        Without this, dropping ``scripts|tests`` from the pattern leaves the whole
        suite green: the proposal tests all sit in exempt documents, so they
        cannot distinguish "the arm exists" from "the arm is absent". Caught by
        mutation testing rather than by reading.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / "dev-docs" / "GUIDE.md").write_text(
                "Run `scripts/check_something_new.py` and "
                "`tests/core/test_not_written_yet.py`.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("check_something_new.py", proc.stderr)
            self.assertIn("test_not_written_yet.py", proc.stderr)

    def test_existing_scripts_and_tests_paths_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / "scripts").mkdir()
            (tmp / "tests").mkdir()
            (tmp / "scripts" / "check_real.py").write_text("x = 1\n")
            (tmp / "tests" / "core").mkdir()
            (tmp / "tests" / "core" / "test_real.py").write_text("x = 1\n")
            (tmp / "dev-docs" / "GUIDE.md").write_text(
                "See `scripts/check_real.py` and `tests/core/test_real.py`.\n"
            )
            self.assertEqual(self._run(tmp).returncode, 0)

    def test_backlog_and_future_work_may_propose_code(self) -> None:
        """TO_DO and FUTURE_WORK name files they intend to create.

        Same rationale as the plan exemption, extended to the two
        forward-looking documents: "Add a `scripts/check_file_line_counts.py`" is a
        proposal, and flagging it would make the gate permanently red.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "TO_DO.md").write_text(
                "Add a `scripts/check_file_line_counts.py` + CI step.\n"
            )
            (dev_docs / "FUTURE_WORK_DETAIL_NOTES.md").write_text(
                "Generate it with `scripts/register_windows.py`.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_githooks_reference_is_matched(self) -> None:
        """Regression: `.githooks/` was unreachable in the pattern.

        The alternation required one or more word characters *before* a directory
        that begins with a dot, so `.githooks/pre-commit` could never match. Every
        other alternative in the set did match, which is why it passed review.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / ".githooks").mkdir(parents=True)
            (tmp / ".githooks" / "pre-commit").write_text("#!/bin/sh\n")
            (tmp / "dev-docs" / "GUIDE.md").write_text(
                "Installed via `.githooks/pre-commit`.\n"
            )
            self.assertEqual(self._run(tmp).returncode, 0)

    def test_missing_githook_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / ".githooks").mkdir(parents=True)
            (tmp / ".githooks" / "pre-push").write_text("#!/bin/sh\n")
            (tmp / "dev-docs" / "GUIDE.md").write_text("Runs `.githooks/gone`.\n")
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("gone", proc.stderr)

    def test_supporting_research_subdirectory_is_scanned(self) -> None:
        """Regression: `supporting.glob` was non-recursive.

        `plans/supporting/research/` holds live analysis. A stale workflow
        reference there was invisible to the checker entirely.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            research = dev_docs / "plans" / "supporting" / "research"
            research.mkdir(parents=True)
            (research / "2026-07-12-note.md").write_text(
                "CI (`.github/workflows/security-checks.yml`).\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("security-checks.yml", proc.stderr)

    def test_snapshot_directories_are_scanned_but_advisory(self) -> None:
        """Dated assessments must be *measured*, not merely ignored.

        Being outside the scanned set is worse than being advisory: a reviewer
        cannot then tell "checked and clean" from "never looked at".
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            for subdir, name in (
                ("safety-scans", "safety-scan-2026-05-30-140016.md"),
                ("security-assessments", "security-assessment-20260415.md"),
                ("doc-assessments", "doc-assessment-2026-04-20.md"),
                ("refactor-assessments", "refactor-assessment-2026-05-25.md"),
            ):
                target = tmp / "dev-docs" / subdir
                target.mkdir(parents=True, exist_ok=True)
                (target / name).write_text("Ran `.github/workflows/grype.yml`.\n")
            self.assertEqual(self._run(tmp).returncode, 0)
            proc = self._run(tmp, "--include-completed-plans")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("safety-scans", proc.stderr)
            self.assertIn("security-assessments", proc.stderr)
            self.assertIn("doc-assessments", proc.stderr)
            self.assertIn("refactor-assessments", proc.stderr)

    def test_dated_records_are_advisory_not_blocking(self) -> None:
        """MAINTENANCE_LOG / SECURITY_IMPLEMENTATION_SUMMARY describe the past."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / "dev-docs" / "MAINTENANCE_LOG.md").write_text(
                "## 2026-01-01\n\nRan `.github/workflows/grype.yml`.\n"
            )
            (tmp / "dev-docs" / "SECURITY_IMPLEMENTATION_SUMMARY.md").write_text(
                "**Date:** 2026-03-22\n\nUsed `.github/workflows/semgrep.yml`.\n"
            )
            self.assertEqual(self._run(tmp).returncode, 0)
            proc = self._run(tmp, "--include-completed-plans")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("MAINTENANCE_LOG.md", proc.stderr)
            self.assertIn("SECURITY_IMPLEMENTATION_SUMMARY.md", proc.stderr)

    def test_advisory_mode_still_blocks_broken_links_in_active_plans(self) -> None:
        """Asking for advisory output must not downgrade the live tree to a warning."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "plans" / "completed" / "DONE.md").write_text(
                "See [gone](../NO_LONGER_THERE.md).\n"
            )
            (dev_docs / "plans" / "ACTIVE.md").write_text(
                "See [also gone](../ALSO_GONE.md).\n"
            )
            proc = self._run(tmp, "--include-completed-plans")
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("Broken documentation references", proc.stderr)


if __name__ == "__main__":
    unittest.main()
