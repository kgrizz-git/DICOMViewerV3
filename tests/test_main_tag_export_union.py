"""
Tag export union background-thread regression tests (Phase 0 safety net).

Exercises ``DICOMViewerApp`` facades around ``TagExportUnionHost`` without
requiring a full tag-export dialog workflow.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from main_test_helpers import with_test_config_manager

import main as main_module


@pytest.mark.qt
def test_get_tag_export_union_snapshot_returns_host_state(tmp_path):
    """Snapshot must reflect the host generation and merged map."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        app.tag_export_union_host.get_snapshot = MagicMock(return_value=(3, {"Tag": "v"}))
        assert app.get_tag_export_union_snapshot() == (3, {"Tag": "v"})
        app.tag_export_union_host.get_snapshot.assert_called_once_with()
    finally:
        restore()


@pytest.mark.qt
def test_drain_tag_export_union_worker_no_worker_completes(tmp_path):
    """Draining with no active worker must return immediately (no deadlock)."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        app.tag_export_union_host.drain_worker = MagicMock()
        app._drain_tag_export_union_worker(timeout_sec=1.0)
        app.tag_export_union_host.drain_worker.assert_called_once_with(1.0)
    finally:
        restore()


@pytest.mark.qt
def test_schedule_tag_export_union_rebuild_delegates_to_host(tmp_path):
    """Rebuild scheduling must reach the union host."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        app.tag_export_union_host.schedule_rebuild = MagicMock()
        app._schedule_tag_export_union_rebuild()
        app.tag_export_union_host.schedule_rebuild.assert_called_once_with()
    finally:
        restore()


@pytest.mark.qt
def test_schedule_rebuild_emits_ready_when_no_studies(tmp_path):
    """Empty study set must emit an immediate ready signal with an empty union."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        app.current_studies = {}
        received: list[tuple[int, object]] = []

        def _on_ready(gen: int, merged: object) -> None:
            received.append((gen, merged))

        app.tag_export_union_ready.connect(_on_ready)
        app._schedule_tag_export_union_rebuild()
        assert len(received) == 1
        gen, merged = received[0]
        assert isinstance(gen, int)
        assert merged == {}
    finally:
        restore()


@pytest.mark.qt
def test_drain_before_reschedule_clears_worker_reference(tmp_path):
    """Scheduling a rebuild must drain any prior worker before starting another."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        drain_calls: list[float] = []

        def _drain(timeout_sec: float = 180.0) -> None:
            drain_calls.append(timeout_sec)
            app.tag_export_union_host._worker = None

        app.tag_export_union_host.drain_worker = _drain
        app.current_studies = {}
        app._schedule_tag_export_union_rebuild()
        assert drain_calls == [180.0]
    finally:
        restore()
