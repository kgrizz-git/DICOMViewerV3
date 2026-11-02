"""Safety checks for the Dependabot hashed-lock recompile workflow.

The workflow runs with the base repository's token. These tests pin the
constraints that keep it from executing a pull request's own code.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW = _ROOT / ".github" / "workflows" / "dependabot-recompile-locks.yml"
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


def test_workflow_trusts_the_base_compiler_and_dependabot_only() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target:" in text
    assert "github.actor == 'dependabot[bot]'" in text
    assert "persist-credentials: false" in text
    assert "git show" in text and "scripts/compile_requirements.py" in text
    assert "--upgrade" not in text
    assert "github.event.pull_request.head.sha" not in text.split("uses: actions/checkout")[1].split("python-version")[0]
    for name in (
        "requirements.in",
        "requirements-dev.in",
        "requirements-build.in",
        "requirements-docs.in",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-build.txt",
        "requirements-docs.txt",
        "requirements-phi-tools.txt",
    ):
        assert f'"{name}"' in text


def test_ci_can_be_dispatched_after_a_token_push() -> None:
    text = _CI.read_text(encoding="utf-8")
    assert "\n  workflow_dispatch:\n" in text
    workflow = _WORKFLOW.read_text(encoding="utf-8")
    assert "gh workflow run ci.yml --ref" in workflow
