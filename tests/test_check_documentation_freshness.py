"""
Tests for scripts/check_documentation_freshness.py.

The check exists because 15 of 23 inventory rows sat at ``Baseline`` for months
with nothing surfacing it. The tests that matter are therefore the ones proving
it *fails* on that state, rather than the ones proving it passes on a tidy one.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "check_documentation_freshness.py"
)
_spec = importlib.util.spec_from_file_location("check_documentation_freshness", _SCRIPT)
assert _spec and _spec.loader
freshness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(freshness)


INVENTORY_HEADER = (
    "| ID | Audience | Canonical | Mirrors | Trigger | Verify | Review state |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
)
TRIAGE_HEADER = (
    "| ID | Signal | Inventory ID | Disposition | Evidence | Follow-up | Reviewed |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
)


def build_repo(
    tmp_path: Path,
    inventory_rows: str,
    triage_rows: str = "",
    assessment: str | None = "doc-assessment-2026-09-05-111057.md",
) -> Path:
    """Minimal repo layout with just the files the check reads."""
    (tmp_path / "dev-docs" / "doc-assessments").mkdir(parents=True)
    (tmp_path / "dev-docs" / "DOCUMENTATION_INVENTORY.md").write_text(
        INVENTORY_HEADER + inventory_rows, encoding="utf-8"
    )
    (tmp_path / "dev-docs" / "DOCUMENTATION_TRIAGE.md").write_text(
        TRIAGE_HEADER + triage_rows, encoding="utf-8"
    )
    if assessment:
        (tmp_path / "dev-docs" / "doc-assessments" / assessment).write_text(
            "# assessment\n", encoding="utf-8"
        )
    return tmp_path


def run(repo: Path, *extra: str) -> int:
    """Invoke the script's main() against a temp repo, the way CI invokes it."""
    argv = [
        "check_documentation_freshness.py",
        "--root",
        str(repo),
        "--today",
        "2026-09-06",
        *extra,
    ]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", argv)
        return freshness.main()


def test_baseline_row_without_deferral_is_reported(tmp_path, capsys):
    """The regression this check exists for: an unowned Baseline row."""
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | — | — | — | Baseline 2026-09-04 |\n",
    )
    assert run(repo, "--strict") == 1
    out = capsys.readouterr().out
    assert "DOC-01" in out
    assert "no open deferred triage row" in out


def test_baseline_row_covered_by_deferral_passes(tmp_path):
    """A Baseline row is acceptable when a deferred row explicitly claims it."""
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | — | — | — | Baseline 2026-09-04 |\n",
        "| TRIAGE-038 | unassessed | DOC-01 | deferred | why | [plan](p.md) | 2026-09-06 |\n",
    )
    assert run(repo, "--strict") == 0


def test_assessed_row_needs_no_deferral(tmp_path):
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | — | — | — | Assessed 2026-09-05 |\n",
    )
    assert run(repo, "--strict") == 0


def test_deferral_without_followup_is_reported(tmp_path, capsys):
    """The ledger makes a bounded follow-up mandatory; verify that is enforced."""
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | — | — | — | Baseline 2026-09-04 |\n",
        "| TRIAGE-038 | unassessed | DOC-01 | deferred | why | — | 2026-09-06 |\n",
    )
    assert run(repo, "--strict") == 1
    assert "has no follow-up" in capsys.readouterr().out


@pytest.mark.parametrize("follow_up", ["TBD", "later", "todo", "N/A", "?", "none"])
def test_deferral_with_placeholder_followup_is_reported(tmp_path, capsys, follow_up):
    """A placeholder bounds the deferral no better than an empty cell."""
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | \u2014 | \u2014 | \u2014 | Baseline 2026-09-04 |\n",
        f"| TRIAGE-038 | unassessed | DOC-01 | deferred | why | {follow_up} | 2026-09-06 |\n",
    )
    assert run(repo, "--strict") == 1
    assert "has no follow-up" in capsys.readouterr().out


def test_deferral_naming_no_inventory_id_is_reported(tmp_path, capsys):
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | — | — | — | Assessed 2026-09-05 |\n",
        "| TRIAGE-039 | orphan | — | deferred | why | [plan](p.md) | 2026-09-06 |\n",
    )
    assert run(repo, "--strict") == 1
    assert "names no inventory ID" in capsys.readouterr().out


def test_stale_assessment_is_reported(tmp_path, capsys):
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | — | — | — | Assessed 2026-09-05 |\n",
        assessment="doc-assessment-2026-01-01-000000.md",
    )
    assert run(repo, "--strict") == 1
    assert "over the 90-day cadence" in capsys.readouterr().out


def test_missing_assessment_directory_is_reported(tmp_path, capsys):
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | — | — | — | Assessed 2026-09-05 |\n",
        assessment=None,
    )
    assert run(repo, "--strict") == 1
    assert "No assessment found" in capsys.readouterr().out


def test_advisory_mode_does_not_fail(tmp_path):
    """Default is warning-only, so it can land in CI without blocking."""
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | — | — | — | Baseline 2026-09-04 |\n",
    )
    assert run(repo) == 0


def test_missing_register_file_exits_two(tmp_path):
    (tmp_path / "dev-docs").mkdir()
    assert run(tmp_path) == 2


def test_separator_rows_are_not_parsed_as_data(tmp_path):
    """A | --- | separator must not be mistaken for an inventory row."""
    states = freshness.inventory_states(
        build_repo(
            tmp_path,
            "| DOC-01 | Users | a.md | — | — | — | Assessed 2026-09-05 |\n",
        )
    )
    assert states == {"DOC-01": "Assessed 2026-09-05"}


@pytest.mark.parametrize(
    "row,expected",
    [
        # Odd backslash count: the pipe is escaped and stays inside the cell.
        (r"| a | b\| c |", ["a", "b| c"]),
        # Even count: the backslash is itself escaped, so the pipe separates.
        (r"| a | b\\| c |", ["a", "b\\", "c"]),
        (r"| a | b | c |", ["a", "b", "c"]),
        (r"| a | | c |", ["a", "", "c"]),
        (r"| a | b", ["a", "b"]),
    ],
)
def test_split_row_pipe_escaping_is_parity_aware(row, expected):
    r"""``\|`` keeps the cell open; ``\\|`` does not.

    A lookbehind for one backslash gets the even case wrong, merging two columns
    and shifting every field after it.
    """
    assert freshness.split_row(row) == expected


def test_escaped_pipe_does_not_shift_cells():
    r"""A cell may embed a literal pipe as ``\|``; splitting on it corrupts the row.

    TRIAGE-039 records shell pipelines in inline code. Without escape handling the
    follow-up column was read from the middle of the evidence text, and the row
    silently passed validation on the wrong cell.
    """
    cells = freshness.split_row(r"| TRIAGE-039 | `git tag \| wc -l` -> 0 | DOC-15 |")
    assert cells == ["TRIAGE-039", "`git tag | wc -l` -> 0", "DOC-15"]


def test_deferred_row_with_escaped_pipe_is_parsed(tmp_path):
    """End to end: an escaped pipe in the evidence cell must not hide the follow-up."""
    repo = build_repo(
        tmp_path,
        "| DOC-01 | Users | a.md | \u2014 | \u2014 | \u2014 | Baseline 2026-09-04 |\n",
        r"| TRIAGE-039 | sig | DOC-01 | deferred | ran `git tag \| wc -l` | [plan](p.md) | 2026-09-06 |"
        + "\n",
    )
    assert run(repo, "--strict") == 0
    assert freshness.deferred_rows(repo)[0][2] == "[plan](p.md)"


@pytest.mark.parametrize(
    "state,expected_baseline",
    [("Baseline 2026-09-04", True), ("Assessed 2026-09-05 (scope note)", False)],
)
def test_review_state_classification(tmp_path, state, expected_baseline):
    repo = build_repo(
        tmp_path, f"| DOC-01 | Users | a.md | — | — | — | {state} |\n"
    )
    states = freshness.inventory_states(repo)
    assert states["DOC-01"].startswith("Baseline") is expected_baseline
