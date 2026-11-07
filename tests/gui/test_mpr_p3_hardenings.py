"""P3 MPR hardenings: empty study UID admission, reservation sweep on close.

See ``dev-docs/plans/completed/MEDIUM_BUG_HUNT_2026-11-04_FIX_PLAN.md`` §Optional P3.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from mpr_lifecycle_harness import _counts, _make_controller

from gui.mpr_admission import admission_summary
from gui.mpr_controller_sessions import reserve_pane_build


@pytest.mark.usefixtures("qapp")
def test_reserve_pane_build_returns_false_without_reserving_when_study_uid_empty() -> None:
    ctrl, _app = _make_controller()
    with patch("gui.mpr_controller_sessions.QMessageBox.warning") as warn:
        ok = reserve_pane_build(ctrl, 0, ("", "SE-1"), pending_bytes=0)
    assert ok is False
    assert warn.called
    msg = warn.call_args[0][2]
    assert admission_summary(ctrl) in msg
    assert _counts(ctrl) == (0, 0, 0, 0)


def test_release_closed_source_sessions_sweeps_orphan_reservations_idempotently() -> None:
    """Pending build token with no pane map entry is cleared; double close is safe."""
    ctrl, _app = _make_controller()
    ctrl._registry.reserve_build("ST", "SE")

    ctrl.release_mpr_for_closed_source("ST", "SE")
    assert ctrl._registry.pending_view_count == 0

    # Second close must not raise (e.g. UnknownSessionError from double discard).
    ctrl.release_mpr_for_closed_source("ST", "SE")
