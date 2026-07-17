"""Tests for staged, advisory privacy-tool dispatch."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import run_conditional_privacy_reviews as reviews


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _stage(repo: Path, path: str, content: bytes = b"synthetic") -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    subprocess.run(["git", "add", "-f", path], cwd=repo, check=True)


def test_staged_paths_are_read_from_index(repo: Path) -> None:
    _stage(repo, "tests/fixtures/sample.json")

    assert reviews.staged_paths(repo) == ["tests/fixtures/sample.json"]


def test_materializes_staged_blob_not_worktree(repo: Path, tmp_path: Path) -> None:
    _stage(repo, "resources/image.png", b"staged")
    (repo / "resources/image.png").write_bytes(b"working-tree")
    output = tmp_path / "opaque.png"

    assert reviews.materialize_index_blob(repo, "resources/image.png", output)
    assert output.read_bytes() == b"staged"


def test_trigger_sets_are_intentionally_narrow() -> None:
    assert ".png" in reviews.OCR_SUFFIXES
    assert ".dcm" in reviews.DICOM_SUFFIXES
    assert ".md" in reviews.DATA_SUFFIXES
    assert "tests/fixtures/" in reviews.DATA_PREFIXES
    assert ".py" not in reviews.DATA_SUFFIXES
