"""Tests for the explicit, direnv-aware development dependency sync."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "scripts" / "sync_dev_environment.py"
_spec = importlib.util.spec_from_file_location("sync_dev_environment", _SCRIPT)
assert _spec and _spec.loader
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("example==1\n", encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text(
        "-r requirements.txt\nscanner==1\n", encoding="utf-8"
    )
    return tmp_path


def test_digest_changes_when_requirements_change(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = sync.requirements_digest(repo)
    (repo / "requirements-dev.txt").write_text("scanner==2\n", encoding="utf-8")

    assert sync.requirements_digest(repo) != before


def test_stamp_round_trip(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir()

    sync.write_stamp(venv, "abc123")

    assert sync.stamp_matches(venv, "abc123")
    assert not sync.stamp_matches(venv, "different")


def test_project_venv_rejects_unrelated_prefix(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".venv").mkdir()

    assert sync.project_venv(repo, tmp_path / "elsewhere") is None


def test_project_venv_accepts_repo_venv(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    venv = repo / ".venv"
    venv.mkdir()

    assert sync.project_venv(repo, venv) == venv.resolve()
