"""
Tag export union background-thread regression tests (Phase 0 safety net).

Exercises ``TagEditingMixin`` facade methods around ``TagExportUnionHost``
without requiring a full ``DICOMViewerApp`` construction for every assertion.

- One smoke test constructs the real ``DICOMViewerApp`` end-to-end.
- Pure delegation tests (drain, schedule) use a lightweight
  ``QObject`` harness with a stub/mock host to verify the mixin forwards
  arguments correctly without any ``TagExportUnionHost`` state.
- Schedule-behaviour tests (empty-studies emission, drain-before-reschedule)
  use the same harness with a real ``TagExportUnionHost`` and a real Qt
  signal to exercise the actual ``schedule_rebuild`` code path.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from main_test_helpers import viewer_app
from PySide6.QtCore import QObject, Signal

from gui.tag_export_union_host import TagExportUnionHost
from main_app_tag_roi import TagEditingMixin

# ---------------------------------------------------------------------------
# Narrow harness: lightweight QObject with TagEditingMixin + real host.
# ---------------------------------------------------------------------------

class _TagExportHarness(QObject, TagEditingMixin):
    """Minimal harness exercising the TagEditingMixin facade methods."""

    tag_export_union_ready = Signal(int, object)

    def __init__(self, host: object) -> None:
        super().__init__()
        self.tag_export_union_host = host
        self.current_studies: dict = {}


# ---------------------------------------------------------------------------
# Narrow harness tests — pure delegation stubs and real-host schedule tests.
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_drain_tag_export_union_worker_no_worker_completes():
    """Drain must forward the timeout to the host's drain_worker exactly."""
    host = MagicMock()
    harness = _TagExportHarness(host)
    harness._drain_tag_export_union_worker(timeout_sec=1.0)
    host.drain_worker.assert_called_once_with(1.0)


@pytest.mark.qt
def test_schedule_tag_export_union_rebuild_delegates_to_host():
    """Rebuild scheduling must reach the union host."""
    host = MagicMock()
    harness = _TagExportHarness(host)
    harness._schedule_tag_export_union_rebuild()
    host.schedule_rebuild.assert_called_once_with()


@pytest.mark.qt
def test_schedule_rebuild_emits_ready_when_no_studies():
    """Empty study set must emit an immediate ready signal with an empty union."""
    host = TagExportUnionHost.__new__(TagExportUnionHost)
    host._worker = None
    host._generation = 0
    harness = _TagExportHarness(host)
    host._app = harness
    harness.current_studies = {}
    received: list[tuple[int, object]] = []

    def _on_ready(gen: int, merged: object) -> None:
        received.append((gen, merged))

    harness.tag_export_union_ready.connect(_on_ready)
    harness._schedule_tag_export_union_rebuild()
    assert len(received) == 1
    gen, merged = received[0]
    assert isinstance(gen, int)
    assert merged == {}


@pytest.mark.qt
def test_drain_before_reschedule_clears_worker_reference():
    """Scheduling a rebuild must drain any prior worker before starting another."""
    host = TagExportUnionHost.__new__(TagExportUnionHost)
    host._worker = object()
    host._generation = 0
    drain_calls: list[float] = []

    def _drain(timeout_sec: float = 180.0) -> None:
        drain_calls.append(timeout_sec)
        host._worker = None

    host.drain_worker = _drain
    harness = _TagExportHarness(host)
    host._app = harness
    harness.current_studies = {}
    harness._schedule_tag_export_union_rebuild()
    assert drain_calls == [180.0]
    assert host._worker is None


# ---------------------------------------------------------------------------
# Smoke test: real DICOMViewerApp construction (1 construction).
# ---------------------------------------------------------------------------

@pytest.mark.qt
def test_get_tag_export_union_snapshot_returns_host_state(tmp_path):
    """Snapshot must reflect the host generation and merged map."""
    with viewer_app(tmp_path) as app:
        app.tag_export_union_host.get_snapshot = MagicMock(
            return_value=(3, {"Tag": "v"})
        )
        assert app.get_tag_export_union_snapshot() == (3, {"Tag": "v"})
        app.tag_export_union_host.get_snapshot.assert_called_once_with()
