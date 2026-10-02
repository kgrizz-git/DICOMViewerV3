"""
Policy tests for ``scripts/check_user_docs_links.py``: which documents are in
the blocking set, which inline-path classes are exempt, and how historical
material is handled.

Split out of ``test_user_docs_links.py`` to keep both files under the repo's
750-line source-size threshold. Same checker, same fixtures, invoked the same
way, so CI and local pytest stay aligned.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_user_docs_links import DOC_SUBDIRS_EXCLUDED, iter_markdown_files

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
        """Every arm of KNOWN_REPO_PATH_PATTERN is exercised in BOTH directions.

        The `.githooks/` arm shipped dead -- it required a word character before a
        dot-directory, so it could never match -- and it shipped because every
        other arm did match while the tests only ever used a workflow path.

        Both directions are required, and the absent direction is the one that
        matters: a name in the *present* list asserts exit 0, which passes
        identically whether the arm matches an existing file or never matches at
        all. A first attempt at this test listed `pytest.ini`, `ruff.toml` and
        `.coveragerc` as present-only, leaving those three arms untested while the
        docstring claimed otherwise -- the same vacuity, one level down. So the
        absent fixture now names real repo filenames that are deliberately *not*
        created, which distinguishes "arm matched and the file is missing" from
        "arm never matched".
        """
        # Names that are arms of the pattern, paired with whether the fixture
        # creates the file.
        arms = [
            ".github/workflows/ci.yml",
            ".github/workflows/ci.yaml",
            "requirements.txt",
            "requirements-dev.txt",
            "pytest.ini",
            "ruff.toml",
            ".coveragerc",
            ".githooks/pre-commit",
        ]
        # NB: the set is *closed*, so `pyproject.toml` / `ruff-x.toml` are
        # deliberately NOT arms -- two plans propose a `pyproject.toml`, and
        # flagging it would be the proposal false positive again.
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / ".github" / "workflows").mkdir(parents=True)
            (tmp / ".githooks").mkdir(parents=True)
            for rel in arms:
                target = tmp / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("name: x\n" if rel.endswith((".yml", ".yaml")) else "x = 1\n")

            def write_guide(names: list[str]) -> None:
                (tmp / "dev-docs" / "GUIDE.md").write_text(
                    "".join(f"See `{n}`.\n" for n in names)
                )

            # Direction 1: every arm names an existing file -> clean.
            write_guide(arms)
            clean = self._run(tmp)
            self.assertEqual(clean.returncode, 0, clean.stderr)

            # Direction 2: every arm names a file that does NOT exist -> each must
            # be reported. Drop any single arm's file from the fixture while the
            # guide still cites it, and that arm must now be flagged.
            for rel in arms:
                (tmp / rel).unlink()
                proc = self._run(tmp)
                self.assertEqual(proc.returncode, 1, f"{rel} deleted, expected failure")
                self.assertIn(rel, proc.stderr)
                target = tmp / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("name: x\n" if rel.endswith((".yml", ".yaml")) else "x = 1\n")
            # Restored: clean again, proving the loop restored state correctly.
            self.assertEqual(self._run(tmp).returncode, 0)

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

    def test_backlog_proposal_must_be_written_as_prose_not_inline_code(self) -> None:
        """TO_DO/FUTURE_WORK are *not* exempt -- the checker's contract is the fix.

        They were briefly exempted, which let 13 descriptive claims in those two
        files rot silently to avoid flagging four correct proposal sentences. The
        contract already prescribed the narrower repair: name a proposed file as
        plain prose, a directory or a glob, not as inline code. Both directions are
        pinned here.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            # Unbackticked proposal: correct prose, not a claim that it exists.
            (dev_docs / "TO_DO.md").write_text(
                "Add a scripts/check_file_line_counts.py + CI step.\n"
            )
            (dev_docs / "FUTURE_WORK_DETAIL_NOTES.md").write_text(
                "Generate it with scripts/register_windows.py.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            # Same names as inline code are now a claim, and a false one.
            (dev_docs / "TO_DO.md").write_text(
                "Add a `scripts/check_file_line_counts.py` + CI step.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("check_file_line_counts.py", proc.stderr)

    def test_descriptive_claims_in_backlog_are_not_silently_unchecked(self) -> None:
        """The 13-descriptive-claims case: real paths in a backlog must still check.

        Guards against re-widening the exemption to fix a future false positive.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (tmp / "scripts").mkdir()
            (tmp / "scripts" / "real_gate.py").write_text("x = 1\n")
            (dev_docs / "TO_DO.md").write_text(
                "Gate runs `scripts/real_gate.py`; see also "
                "`scripts/never_written.py`.\n"
            )
            proc = self._run(tmp)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("never_written.py", proc.stderr)
            self.assertNotIn("real_gate.py", proc.stderr)

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

    def test_nested_completed_plan_is_scanned_advisory_not_invisible(self) -> None:
        """The advisory scan of ``completed/`` must recurse, matching the exclusion.

        ``_is_excluded`` treats the whole ``completed/`` subtree as historical via
        ``is_relative_to``, but the advisory glob was non-recursive. A nested plan
        would therefore be excluded from the blocking pass *and* never scanned --
        invisible, which is the worse failure the whole snapshot-directory change
        was made to avoid. Correct today only because no subdirectory exists yet,
        which is how the dead ``.githooks/`` arm and the non-recursive
        ``supporting/`` glob both survived review.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            nested = tmp / "dev-docs" / "plans" / "completed" / "2026"
            nested.mkdir(parents=True)
            (nested / "NESTED.md").write_text("Ran `.github/workflows/grype.yml`.\n")
            top = tmp / "dev-docs" / "plans" / "completed" / "OLD.md"
            top.write_text("Ran `.github/workflows/grype.yml`.\n")

            # Not blocking: a completed plan describes the tree as it was.
            blocked = self._run(tmp)
            self.assertEqual(blocked.returncode, 0, blocked.stderr)

            # Both the top-level and the nested plan must be measured.
            proc = self._run(tmp, "--include-completed-plans")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("completed/OLD.md", proc.stderr)
            self.assertIn("completed/2026/NESTED.md", proc.stderr)

    def test_advisory_report_survives_live_errors(self) -> None:
        """Advisory output must not be discarded when live-document rot exists.

        The blocking branch used to ``return 1`` immediately, dropping the
        advisory list. An advisory run with live rot therefore printed no
        historical figure at all -- silent on exactly the runs where the debt
        number is most worth reading, and it made the advisory CI step go quiet
        whenever a real regression was in progress.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "info" / "A.md").write_text(
                "See `.github/workflows/gone.yml`.\n"
            )
            (dev_docs / "plans" / "completed" / "OLD.md").write_text(
                "See `.github/workflows/grype.yml`.\n"
            )
            proc = self._run(tmp, "--include-completed-plans")
            # Historical rot never affects status; live-document rot still does.
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("gone.yml", proc.stderr)
            self.assertIn("grype.yml", proc.stderr)
            self.assertIn("completed/OLD.md", proc.stderr)

    def test_advisory_banner_does_not_claim_ok_when_blocking(self) -> None:
        """The advisory header must not read as success on a failing run.

        Reporting advisory output ahead of the status decision means the header
        can follow a "Broken documentation references" block. When it still led
        with "OK:", a reader scanning stderr could take the whole run as clean.
        Exit status was never wrong; the wording was.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "info" / "A.md").write_text(
                "See `.github/workflows/gone.yml`.\n"
            )
            (dev_docs / "plans" / "completed" / "OLD.md").write_text(
                "See `.github/workflows/grype.yml`.\n"
            )
            proc = self._run(tmp, "--include-completed-plans")
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertNotIn("OK:", proc.stderr)
            self.assertIn("live-document rot above is blocking", proc.stderr)

            # A clean run keeps its OK banner -- the wording is only a problem when
            # blocking findings are present. NB the all-clear banner goes to stdout
            # while the advisory header goes to stderr; they are not symmetric.
            clean_tree = Path(tempfile.mkdtemp())
            self._tree(clean_tree)
            ok = self._run(clean_tree)
            self.assertEqual(ok.returncode, 0)
            self.assertIn("OK:", ok.stdout)

    def test_live_errors_still_exit_1_in_advisory_mode(self) -> None:
        """`--include-completed-plans` must not imply a guaranteed exit 0."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            (dev_docs / "info" / "A.md").write_text(
                "See `.github/workflows/gone.yml`.\n"
            )
            self.assertEqual(self._run(tmp, "--include-completed-plans").returncode, 1)
            self.assertEqual(self._run(tmp).returncode, 1)

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

    def test_every_dev_docs_subdirectory_is_either_scanned_or_listed(self) -> None:
        """No `dev-docs/**` subdirectory may fall outside the scan set silently.

        Seven directories had never been added at all — not excluded on purpose,
        simply absent — hiding 12 stale `src/` references. Outside the scanned set
        a reviewer cannot distinguish "checked and clean" from "never looked at",
        so every subdirectory holding Markdown must be accounted for: scanned, or
        named in SNAPSHOT_SUBDIRS / HISTORICAL_RECORD_FILES.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dev_docs = self._tree(tmp)
            # A directory nobody claimed.
            (dev_docs / "bug-investigations").mkdir()
            (dev_docs / "bug-investigations" / "INV.md").write_text(
                "See `.github/workflows/grype.yml`.\n"
            )
            # Advisory by default (the real repo has no rot in these, but the
            # classification is what is under test).
            self.assertEqual(self._run(tmp).returncode, 0)
            proc = self._run(tmp, "--include-completed-plans")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("bug-investigations", proc.stderr)

    def test_nested_agents_instructions_are_scanned_and_blocking(self) -> None:
        """Nested `AGENTS.md` files under src/ are live, so they block.

        The root AGENTS.md tells agents to run named scripts and paths. A nested
        instruction file naming a module that has moved sends the next agent to a
        file that is not there. Adding these to the scan set immediately surfaced
        `src/qa/AGENTS.md` naming `src/core/qa_app_facade.py` when the facade
        lives in `src/gui/`.
        """
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self._tree(tmp)
            (tmp / "src" / "qa").mkdir(parents=True, exist_ok=True)
            (tmp / "src" / "qa" / "AGENTS.md").write_text(
                "Start at `src/core/qa_app_facade.py`.\n"
            )
            blocked = self._run(tmp)
            self.assertEqual(blocked.returncode, 1, blocked.stderr)
            self.assertIn("qa_app_facade.py", blocked.stderr)

    def test_real_repo_no_tracked_markdown_is_invisible(self) -> None:
        """Exhaustive guard: only the documented exclusions may escape scanning.

        Sixteen tracked Markdown files were invisible -- SECURITY.md, DESIGN.md,
        CODE_OF_CONDUCT.md, .github/CONTRIBUTING.md, .github/PULL_REQUEST_TEMPLATE.md,
        tests/README.md, five tests/fixtures/*/README.md, security/*.md and
        tools/sonarqube/README.md. All sixteen turned out to be clean, so this closes
        a risk rather than fixing rot, which is worth keeping precisely because the
        gap was invisible in both directions: nothing reported those files and
        nothing checked them.

        Lists tracked files with ``git ls-files`` rather than walking the disk.
        A walk sees every contributor's untracked tool caches, so it either
        prunes hidden directories wholesale (hiding a new tracked dot-directory)
        or fails on whatever a given machine happens to hold. Git answers the
        question the test is actually asking. CI checks out with git; the test
        skips only when no git binary or work tree is available.
        """
        repo_root = Path(__file__).resolve().parents[1]
        # Skip only for the two cases that genuinely cannot answer. Any other git
        # failure (e.g. "dubious ownership" under a different UID) must fail, or
        # the guard silently stops running while the job stays green.
        if shutil.which("git") is None:  # pragma: no cover - CI always has git
            self.skipTest("git is not available")
        if not (repo_root / ".git").exists():  # pragma: no cover - source export
            self.skipTest("not running inside a git work tree")
        # An inherited GIT_DIR / GIT_INDEX_FILE (pytest launched from a hook)
        # would list a different index than this checkout's. Only the
        # redirection variables go: GIT_CONFIG_* may carry a safe.directory
        # grant that a different-UID container needs.
        redirects = {
            "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        }
        env = {k: v for k, v in os.environ.items() if k not in redirects}
        listed = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z", "--", "*.md"],
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            env=env,
            check=False,
        )
        if listed.returncode != 0:
            self.fail(f"git ls-files failed: {listed.stderr.strip()}")
        # Deliberately out of scope: agent tooling configuration owned by other
        # tools, not documentation of this project, plus the checker's own
        # policy exclusion, imported so the two cannot drift apart.
        allowed_unscanned = tuple(
            f"{d}/" for d in (".agents", ".claude", ".cursor", *DOC_SUBDIRS_EXCLUDED)
        )

        scanned = {f.resolve() for f in iter_markdown_files(repo_root, True)}
        invisible = [
            rel
            for rel in listed.stdout.split("\0")
            if rel
            and not rel.startswith(allowed_unscanned)
            # A tracked file deleted in the working tree is not scannable yet.
            and (repo_root / rel).is_file()
            and (repo_root / rel).resolve() not in scanned
        ]
        self.assertEqual(invisible, [], f"invisible Markdown: {sorted(invisible)}")

    def test_real_repo_nested_agents_files_are_all_scanned(self) -> None:
        """Real-repo guard: no `src/**/AGENTS.md` may escape the scan set."""
        repo_root = Path(__file__).resolve().parents[1]
        src_dir = repo_root / "src"
        if not src_dir.is_dir():  # pragma: no cover - only if run outside the repo
            self.skipTest("not running inside the repository")
        scanned = set(iter_markdown_files(repo_root, True))
        missed = {
            str(f.relative_to(repo_root))
            for f in src_dir.rglob("AGENTS.md")
            if f.resolve() not in scanned
        }
        self.assertEqual(missed, set(), f"unscanned nested AGENTS.md: {missed}")

    def test_real_repo_has_no_unclassified_dev_docs_subdirectory(self) -> None:
        """Runs against the real repository, not a fixture.

        A fixture cannot catch a directory that exists only in the repo, which is
        exactly how the seven were missed. Any `dev-docs/` subdirectory holding
        Markdown must be scanned by iter_markdown_files.
        """
        repo_root = Path(__file__).resolve().parents[1]
        dev_docs = repo_root / "dev-docs"
        if not dev_docs.is_dir():  # pragma: no cover - only if run outside the repo
            self.skipTest("not running inside the repository")
        scanned = set()
        for f in iter_markdown_files(repo_root, True):
            parts = f.relative_to(repo_root).parts
            if len(parts) > 2 and parts[0] == "dev-docs":
                scanned.add(parts[1])
        unclassified = {
            d.name
            for d in dev_docs.iterdir()
            if d.is_dir() and list(d.rglob("*.md")) and d.name not in scanned
        }
        self.assertEqual(
            unclassified, set(), f"unscanned dev-docs subdirectories: {unclassified}"
        )

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
