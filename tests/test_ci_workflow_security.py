"""Regression checks for CI workflow security controls."""

from pathlib import Path

CI_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def test_coderabbit_deduplication_accepts_only_the_actions_bot_marker() -> None:
    """An untrusted PR comment must not suppress a CodeRabbit review request."""
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "comment.user?.login === 'github-actions[bot]'" in workflow
    assert "comment.user?.type === 'Bot'" in workflow
    assert "comment.body?.includes(marker)" in workflow
