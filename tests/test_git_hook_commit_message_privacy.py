"""Regression tests for the commit-message PHI/PII privacy hook."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "git_hook_commit_message_privacy.py"
)
SPEC = importlib.util.spec_from_file_location("git_hook_commit_message_privacy", SCRIPT)
assert SPEC and SPEC.loader
commit_privacy = importlib.util.module_from_spec(SPEC)
sys.modules["git_hook_commit_message_privacy"] = commit_privacy
SPEC.loader.exec_module(commit_privacy)


@pytest.mark.parametrize(
    "message",
    [
        r"Fix path C:\Users\developer\Desktop\study.dcm",
        "Connect to 192.168.1.15 for verification",
        "Connect to fd00::15 for verification",
        "Use dicom://pacs.internal for verification",
        "Fix MRN: ABCD-1234 import",
    ],
)
def test_blocks_sensitive_commit_message_content(message: str) -> None:
    assert commit_privacy.check_message(message, frozenset())


def test_blocks_configured_local_identity() -> None:
    violations = commit_privacy.check_message(
        "Fix issue on workstation-alpha", frozenset({"workstation-alpha"})
    )
    assert violations == [(1, "local account or hostname")]


def test_allows_generic_safe_commit_message() -> None:
    assert (
        commit_privacy.check_message(
            "Harden synthetic DICOM fixture checks for 192.0.2.10", frozenset()
        )
        == []
    )


def test_main_redacts_matched_message_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    message_file = tmp_path / "message"
    message_file.write_text(
        r"Fix C:\Users\developer\Desktop\study.dcm", encoding="utf-8"
    )
    monkeypatch.setattr(commit_privacy, "local_identities", lambda: frozenset())

    assert commit_privacy.main([str(message_file)]) == 1
    stderr = capsys.readouterr().err
    assert "machine-specific path" in stderr
    assert "developer" not in stderr
