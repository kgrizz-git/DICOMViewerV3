"""Unit tests for ``scripts/git-hook-prune-backups.py`` intent-age helpers."""

from __future__ import annotations

import importlib.util
import os
from datetime import datetime
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "git-hook-prune-backups.py"


def _load_prune_module():
    spec = importlib.util.spec_from_file_location("git_hook_prune_backups", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def prune():
    return _load_prune_module()


def test_newest_embedded_none(prune):
    assert prune.newest_embedded_yyyymmdd_datetime("no_digits_here.txt") is None


def test_newest_embedded_picks_newest(prune):
    fixed = datetime(2026, 6, 1, 12, 0, 0)
    got = prune.newest_embedded_yyyymmdd_datetime(
        "backups/foo_pre_20250102_bar_20260315_end.py",
        now=fixed,
    )
    assert got == datetime(2026, 3, 15, 0, 0, 0)


def test_newest_embedded_ignores_future_dates(prune):
    fixed = datetime(2026, 1, 10, 0, 0, 0)
    got = prune.newest_embedded_yyyymmdd_datetime("bak-20990101-wrong.txt", now=fixed)
    assert got is None


def test_backup_intent_tracked_prefers_git(prune, tmp_path: Path):
    path = tmp_path / "x.bak"
    path.write_text("x", encoding="utf-8")
    git_dt = datetime(2020, 1, 2, 0, 0, 0)
    os.utime(path, (git_dt.timestamp(), git_dt.timestamp()))
    got = prune.backup_intent_datetime(
        path,
        rel_posix="backups/x.bak",
        tracked=True,
        git_latest={"backups/x.bak": git_dt},
        now=datetime(2026, 1, 1),
    )
    assert got == git_dt


def test_backup_intent_tracked_missing_git_uses_mtime(prune, tmp_path: Path):
    path = tmp_path / "y.bak"
    path.write_text("y", encoding="utf-8")
    mt = datetime(2024, 5, 6, 0, 0, 0)
    os.utime(path, (mt.timestamp(), mt.timestamp()))
    got = prune.backup_intent_datetime(
        path,
        rel_posix="backups/y.bak",
        tracked=True,
        git_latest={},
        now=datetime(2026, 1, 1),
    )
    assert got == mt


def test_backup_intent_untracked_max_embedded_and_mtime(prune, tmp_path: Path):
    path = tmp_path / "pre_20200101_stale_name.py"
    path.write_text("z", encoding="utf-8")
    mt = datetime(2026, 4, 1, 0, 0, 0)
    os.utime(path, (mt.timestamp(), mt.timestamp()))
    got = prune.backup_intent_datetime(
        path,
        rel_posix="backups/pre_20200101_stale_name.py",
        tracked=False,
        git_latest={},
        now=datetime(2026, 6, 1),
    )
    assert got == mt
