"""Unit tests for ``scripts/git-hook-prune-backups.py`` intent-age and prune rules."""

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


def _h40() -> str:
    return "a" * 40


def test_backup_intent_tracked_prefers_git(prune, tmp_path: Path):
    path = tmp_path / "x.bak"
    path.write_text("x", encoding="utf-8")
    git_dt = datetime(2020, 1, 2, 0, 0, 0)
    os.utime(path, (git_dt.timestamp(), git_dt.timestamp()))
    got = prune.backup_intent_datetime(
        path,
        rel_posix="backups/x.bak",
        tracked=True,
        git_touch={"backups/x.bak": (_h40(), git_dt)},
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
        git_touch={},
        now=datetime(2026, 1, 1),
    )
    assert got == mt


def test_backup_intent_untracked_uses_older_of_embedded_and_mtime(prune, tmp_path: Path):
    path = tmp_path / "pre_20200101_stale_name.py"
    path.write_text("z", encoding="utf-8")
    mt = datetime(2026, 4, 1, 0, 0, 0)
    os.utime(path, (mt.timestamp(), mt.timestamp()))
    got = prune.backup_intent_datetime(
        path,
        rel_posix="backups/pre_20200101_stale_name.py",
        tracked=False,
        git_touch={},
        now=datetime(2026, 6, 1),
    )
    assert got == datetime(2020, 1, 1, 0, 0, 0)


def test_backup_intent_untracked_uses_older_mtime_when_embedded_is_newer(prune, tmp_path: Path):
    path = tmp_path / "recent_name_20260414.py"
    path.write_text("z", encoding="utf-8")
    mt = datetime(2019, 6, 1, 12, 0, 0)
    os.utime(path, (mt.timestamp(), mt.timestamp()))
    got = prune.backup_intent_datetime(
        path,
        rel_posix="backups/recent_name_20260414.py",
        tracked=False,
        git_touch={},
        now=datetime(2026, 6, 1),
    )
    assert got == mt


def test_tracked_prune_low_velocity_commits_only(prune):
    cutoff = datetime(2026, 4, 1, 0, 0, 0)
    intent = datetime(2020, 1, 1, 0, 0, 0)
    assert not prune.tracked_should_prune(
        commits_since_touch=5,
        intent=intent,
        cutoff=cutoff,
        commits_in_window=3,
        max_commits=10,
        velocity_threshold=10,
    )
    assert prune.tracked_should_prune(
        commits_since_touch=11,
        intent=intent,
        cutoff=cutoff,
        commits_in_window=3,
        max_commits=10,
        velocity_threshold=10,
    )


def test_tracked_prune_high_velocity_time_cutoff(prune):
    cutoff = datetime(2026, 4, 1, 0, 0, 0)
    old = datetime(2026, 3, 1, 0, 0, 0)
    fresh = datetime(2026, 4, 2, 0, 0, 0)
    assert prune.tracked_should_prune(
        commits_since_touch=3,
        intent=old,
        cutoff=cutoff,
        commits_in_window=11,
        max_commits=10,
        velocity_threshold=10,
    )
    assert not prune.tracked_should_prune(
        commits_since_touch=3,
        intent=fresh,
        cutoff=cutoff,
        commits_in_window=11,
        max_commits=10,
        velocity_threshold=10,
    )


def test_tracked_prune_no_touch_commit_falls_back_to_days(prune):
    cutoff = datetime(2026, 4, 1, 0, 0, 0)
    assert prune.tracked_should_prune(
        commits_since_touch=None,
        intent=datetime(2026, 3, 1, 0, 0, 0),
        cutoff=cutoff,
        commits_in_window=0,
        max_commits=10,
        velocity_threshold=10,
    )
    assert not prune.tracked_should_prune(
        commits_since_touch=None,
        intent=datetime(2026, 4, 2, 0, 0, 0),
        cutoff=cutoff,
        commits_in_window=0,
        max_commits=10,
        velocity_threshold=10,
    )


def test_tracked_prune_max_commits_zero_disables_depth_rule(prune):
    cutoff = datetime(2026, 4, 1, 0, 0, 0)
    intent = datetime(2020, 1, 1, 0, 0, 0)
    assert not prune.tracked_should_prune(
        commits_since_touch=50,
        intent=intent,
        cutoff=cutoff,
        commits_in_window=3,
        max_commits=0,
        velocity_threshold=10,
    )
