"""
Tests for LoadingProgressManager and ProgressDialogEventFilter.

Covers:
    - start_animated_loading / stop_animated_loading lifecycle.
    - on_cancel_loading sets is_cancelled() and invokes the cancel callback.
    - reset() clears all state.
    - create_progress_dialog returns a QProgressDialog with correct settings.
    - was_dialog_cancelled() reflects the dialog's cancelled state.
    - get_dialog() returns None before creation and after close.

Requirements:
    - pytest-qt (qapp fixture) for a live QApplication.
    - PySide6 for Qt widgets.
"""

import pytest
from unittest.mock import MagicMock, patch

from core.loading_progress_manager import LoadingProgressManager, ProgressDialogEventFilter
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QProgressDialog, QWidget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(
    status_callback=None,
    cancel_callback=None,
) -> LoadingProgressManager:
    """Return a LoadingProgressManager wired with simple mock callbacks."""
    if status_callback is None:
        status_callback = MagicMock()
    return LoadingProgressManager(
        update_status_callback=status_callback,
        cancel_loader_callback=cancel_callback,
    )


# ---------------------------------------------------------------------------
# Animated loading
# ---------------------------------------------------------------------------

class TestStartStopAnimatedLoading:
    """Tests for the animated loading-dots timer."""

    def test_start_creates_timer(self, qapp):
        mgr = _make_manager()
        mgr.start_animated_loading("Loading")
        try:
            assert mgr._loading_timer is not None
            assert mgr._loading_timer.isActive()
            assert mgr._loading_base_message == "Loading"
        finally:
            mgr.stop_animated_loading()

    def test_start_calls_status_callback_immediately(self, qapp):
        cb = MagicMock()
        mgr = _make_manager(status_callback=cb)
        mgr.start_animated_loading("Test")
        # One call is made right away (first dot frame).
        assert cb.call_count >= 1
        # The message should start with the base text.
        first_msg = cb.call_args_list[0][0][0]
        assert first_msg.startswith("Test")
        mgr.stop_animated_loading()

    def test_stop_removes_timer(self, qapp):
        mgr = _make_manager()
        mgr.start_animated_loading("Loading")
        mgr.stop_animated_loading()
        assert mgr._loading_timer is None
        assert mgr._loading_base_message == ""
        assert mgr._loading_dot_state == 0

    def test_start_twice_does_not_leak_timer(self, qapp):
        """Starting twice should stop the first timer before creating a new one."""
        mgr = _make_manager()
        mgr.start_animated_loading("First")
        first_timer = mgr._loading_timer
        mgr.start_animated_loading("Second")
        try:
            second_timer = mgr._loading_timer
            assert second_timer is not first_timer
            assert mgr._loading_timer.isActive()
        finally:
            mgr.stop_animated_loading()

    def test_stop_when_not_started_is_safe(self, qapp):
        mgr = _make_manager()
        mgr.stop_animated_loading()  # should not raise
        assert mgr._loading_timer is None


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

class TestCancellation:
    """Tests for on_cancel_loading / is_cancelled."""

    def test_initially_not_cancelled(self, qapp):
        mgr = _make_manager()
        assert mgr.is_cancelled() is False

    def test_on_cancel_sets_flag(self, qapp):
        mgr = _make_manager()
        mgr.on_cancel_loading()
        assert mgr.is_cancelled() is True

    def test_on_cancel_invokes_cancel_callback(self, qapp):
        cancel_cb = MagicMock()
        mgr = _make_manager(cancel_callback=cancel_cb)
        mgr.on_cancel_loading()
        cancel_cb.assert_called_once()

    def test_on_cancel_without_callback_does_not_raise(self, qapp):
        mgr = _make_manager(cancel_callback=None)
        mgr.on_cancel_loading()  # should not raise
        assert mgr.is_cancelled() is True

    def test_on_cancel_posts_cancelling_status(self, qapp):
        cb = MagicMock()
        mgr = _make_manager(status_callback=cb)
        mgr.on_cancel_loading()
        messages = [c[0][0] for c in cb.call_args_list]
        assert any("Cancelling" in m for m in messages)

    def test_on_cancel_stops_animation(self, qapp):
        mgr = _make_manager()
        mgr.start_animated_loading("Loading")
        assert mgr._loading_timer is not None
        mgr.on_cancel_loading()
        assert mgr._loading_timer is None


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    """Tests for reset()."""

    def test_reset_clears_cancelled_flag(self, qapp):
        mgr = _make_manager()
        mgr.on_cancel_loading()
        assert mgr.is_cancelled() is True
        mgr.reset()
        assert mgr.is_cancelled() is False

    def test_reset_stops_timer(self, qapp):
        mgr = _make_manager()
        mgr.start_animated_loading("Loading")
        mgr.reset()
        assert mgr._loading_timer is None

    def test_reset_closes_dialog(self, qapp):
        mgr = _make_manager()
        w = QWidget()
        mgr.create_progress_dialog(w, 10, "test")
        assert mgr.get_dialog() is not None
        mgr.reset()
        assert mgr.get_dialog() is None
        w.close()

    def test_reset_from_clean_state_is_idempotent(self, qapp):
        mgr = _make_manager()
        mgr.reset()
        mgr.reset()
        assert mgr.is_cancelled() is False
        assert mgr.get_dialog() is None
        assert mgr._loading_timer is None


# ---------------------------------------------------------------------------
# Progress dialog
# ---------------------------------------------------------------------------

class TestProgressDialog:
    """Tests for create_progress_dialog / close_progress_dialog / get_dialog."""

    def test_create_returns_progress_dialog(self, qapp):
        mgr = _make_manager()
        w = QWidget()
        dlg = mgr.create_progress_dialog(w, 5, "Loading...")
        try:
            assert isinstance(dlg, QProgressDialog)
        finally:
            mgr.close_progress_dialog()
            w.close()

    def test_get_dialog_returns_same_instance(self, qapp):
        mgr = _make_manager()
        w = QWidget()
        dlg = mgr.create_progress_dialog(w, 5, "Loading...")
        try:
            assert mgr.get_dialog() is dlg
        finally:
            mgr.close_progress_dialog()
            w.close()

    def test_get_dialog_none_before_creation(self, qapp):
        mgr = _make_manager()
        assert mgr.get_dialog() is None

    def test_get_dialog_none_after_close(self, qapp):
        mgr = _make_manager()
        w = QWidget()
        mgr.create_progress_dialog(w, 5, "Loading...")
        mgr.close_progress_dialog()
        assert mgr.get_dialog() is None
        w.close()

    def test_create_with_zero_total_clamps_to_one(self, qapp):
        mgr = _make_manager()
        w = QWidget()
        dlg = mgr.create_progress_dialog(w, 0, "Loading...")
        try:
            assert dlg.maximum() >= 1
        finally:
            mgr.close_progress_dialog()
            w.close()

    def test_create_closes_previous_dialog(self, qapp):
        mgr = _make_manager()
        w = QWidget()
        dlg1 = mgr.create_progress_dialog(w, 5, "First")
        dlg2 = mgr.create_progress_dialog(w, 10, "Second")
        try:
            assert mgr.get_dialog() is dlg2
            assert dlg2 is not dlg1
        finally:
            mgr.close_progress_dialog()
            w.close()

    def test_was_dialog_cancelled_false_initially(self, qapp):
        mgr = _make_manager()
        w = QWidget()
        mgr.create_progress_dialog(w, 5, "Loading...")
        try:
            assert mgr.was_dialog_cancelled() is False
        finally:
            mgr.close_progress_dialog()
            w.close()

    def test_was_dialog_cancelled_false_when_no_dialog(self, qapp):
        mgr = _make_manager()
        assert mgr.was_dialog_cancelled() is False

    def test_close_without_dialog_is_safe(self, qapp):
        mgr = _make_manager()
        mgr.close_progress_dialog()  # should not raise


# ---------------------------------------------------------------------------
# ProgressDialogEventFilter
# ---------------------------------------------------------------------------

class TestProgressDialogEventFilter:
    """Tests for the Escape-key event filter."""

    def test_escape_invokes_callback(self, qapp):
        cb = MagicMock()
        ef = ProgressDialogEventFilter(cb)
        event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,  # type: ignore[attr-defined]
            Qt.KeyboardModifier.NoModifier,
        )
        result = ef.eventFilter(None, event)
        cb.assert_called_once()
        assert result is True

    def test_other_key_does_not_invoke_callback(self, qapp):
        cb = MagicMock()
        ef = ProgressDialogEventFilter(cb)
        event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Return,  # type: ignore[attr-defined]
            Qt.KeyboardModifier.NoModifier,
        )
        result = ef.eventFilter(None, event)
        cb.assert_not_called()
        assert result is False

    def test_non_keypress_event_returns_false(self, qapp):
        cb = MagicMock()
        ef = ProgressDialogEventFilter(cb)
        event = QEvent(QEvent.Type.MouseMove)
        result = ef.eventFilter(None, event)
        cb.assert_not_called()
        assert result is False
