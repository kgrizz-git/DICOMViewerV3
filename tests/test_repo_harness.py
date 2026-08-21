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


class TestLauncherVenvResolution(unittest.TestCase):
    """Unit-test shared venv candidate order across launchers and scan-security.ps1."""

    def test_repo_launchers_match_expected_order(self) -> None:
        module = _load_harness_module()
        errors = module.check_launcher_venv_resolution(REPO_ROOT)
        self.assertEqual(errors, [])

    def test_detects_diverging_candidate_orders(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "launch.bat").write_text(
                'if exist "%ROOT%venv\\Scripts\\python.exe" set "VENV=%ROOT%venv"\n'
                'if not defined VENV if exist "%ROOT%.venv\\Scripts\\python.exe" '
                'set "VENV=%ROOT%.venv"\n'
                'if not defined VENV set "VENV=%ROOT%.venv"\n',
                encoding="utf-8",
            )
            (root / "launch.command").write_text(
                "for candidate in .venv venv env virtualenv; do\n"
                'VENV="$SCRIPT_DIR/.venv"\n',
                encoding="utf-8",
            )
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "scan-security.ps1").write_text(
                'foreach ($name in @(".venv", "venv", "env", "virtualenv")) {\n',
                encoding="utf-8",
            )
            errors = module.check_launcher_venv_resolution(root)
        self.assertTrue(any("launch.bat venv candidate order" in e for e in errors))
        self.assertTrue(any("diverge" in e for e in errors))

    def test_detects_scan_security_ps1_order_drift(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "launch.bat").write_text(
                'if exist "%ROOT%.venv\\Scripts\\python.exe" set "VENV=%ROOT%.venv"\n'
                'if not defined VENV if exist "%ROOT%venv\\Scripts\\python.exe" '
                'set "VENV=%ROOT%venv"\n'
                'if not defined VENV if exist "%ROOT%env\\Scripts\\python.exe" '
                'set "VENV=%ROOT%env"\n'
                'if not defined VENV if exist "%ROOT%virtualenv\\Scripts\\python.exe" '
                'set "VENV=%ROOT%virtualenv"\n'
                'if not defined VENV set "VENV=%ROOT%.venv"\n',
                encoding="utf-8",
            )
            (root / "launch.command").write_text(
                "for candidate in .venv venv env virtualenv; do\n"
                'VENV="$SCRIPT_DIR/.venv"\n',
                encoding="utf-8",
            )
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "scan-security.ps1").write_text(
                'foreach ($name in @(".venv", "venv")) {\n',
                encoding="utf-8",
            )
            errors = module.check_launcher_venv_resolution(root)
        self.assertTrue(
            any("scripts/scan-security.ps1 venv candidate order" in e for e in errors)
        )


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


class TestExternalAnalysisUploadPolicy(unittest.TestCase):
    """Unit-test the local-first coverage and analysis policy."""

    def test_rejects_external_config_and_workflow_action(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (root / "codecov.yml").write_text("coverage: {}\n", encoding="utf-8")
            (workflows / "tests.yml").write_text(
                "steps:\n  - uses: codecov/codecov-action@v5\n",
                encoding="utf-8",
            )

            errors = module.check_external_analysis_upload_policy(root)

        self.assertEqual(len(errors), 2)
        self.assertTrue(any("codecov.yml" in error for error in errors))
        self.assertTrue(any("codecov/codecov-action" in error for error in errors))

    def test_accepts_console_only_local_coverage(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "tests.yml").write_text(
                "steps:\n  - run: python -m pytest --cov=src --cov-report=term\n",
                encoding="utf-8",
            )

            errors = module.check_external_analysis_upload_policy(root)

        self.assertEqual(errors, [])

    def test_accepts_dormant_sonarcloud_scope_without_a_workflow(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".sonarcloud.properties").write_text(
                "sonar.sources=src\n", encoding="utf-8"
            )

            errors = module.check_external_analysis_upload_policy(root)

        self.assertEqual(errors, [])

    def test_accepts_reviewed_main_only_sonarqube_cloud_workflow(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text(
                "on:\n"
                "  push:\n"
                "    branches: [main, develop]\n"
                "jobs:\n"
                "  sonarqube:\n"
                "    needs: [privacy-gates]\n"
                "    if: github.event_name == 'push' && (github.ref == 'refs/heads/main')\n"
                "    steps:\n"
                "      - uses: actions/checkout@v7\n"
                "        with:\n"
                "          fetch-depth: 0\n"
                "          persist-credentials: false\n"
                "      - uses: SonarSource/sonarqube-scan-action@"
                "7006c4492b2e0ee0f816d36501671557c97f5995\n"
                "        env:\n"
                "          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}\n",
                encoding="utf-8",
            )

            errors = module.check_external_analysis_upload_policy(root)

        self.assertEqual(errors, [])

    def test_rejects_sonarqube_cloud_workflow_without_privacy_gate(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "sonarqube-cloud-main.yml").write_text(
                "on:\n  pull_request:\n"
                "steps:\n"
                "  - uses: SonarSource/sonarqube-scan-action@"
                "7006c4492b2e0ee0f816d36501671557c97f5995\n",
                encoding="utf-8",
            )

            errors = module.check_external_analysis_upload_policy(root)

        self.assertEqual(len(errors), 1)
        self.assertIn("sonarqube-scan-action", errors[0])

    def test_rejects_secret_verification_against_provider_apis(self) -> None:
        import tempfile

        module = _load_harness_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "secrets.yml").write_text(
                "steps:\n  - run: trufflehog filesystem . --only-verified\n",
                encoding="utf-8",
            )

            errors = module.check_external_analysis_upload_policy(root)

        self.assertEqual(len(errors), 1)
        self.assertIn("network verification", errors[0])


if __name__ == "__main__":
    unittest.main()
