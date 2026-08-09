"""
Unit tests for ``gui.dialogs.cine_export_encode_thread.CineVideoEncodeThread``.

Mocks ``encode_cine_video_from_png_paths`` to exercise the success, failure,
and cancellation signal paths without invoking FFmpeg.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QTimer

from gui.dialogs.cine_export_encode_thread import CineVideoEncodeThread

pytestmark = pytest.mark.qt


def _make_thread(cancel_set: bool = False, paths=("a.png", "b.png")):
    cancel_event = MagicMock()
    cancel_event.is_set.return_value = cancel_set
    return CineVideoEncodeThread(
        png_paths=[Path(p) for p in paths],
        output_path="/tmp/out.mp4",
        video_format="mp4",
        fps=10.0,
        cancel_event=cancel_event,
    ), cancel_event


def _run_and_wait(thread: CineVideoEncodeThread, qapp) -> tuple[bool, list[str]]:
    succeeded: list[bool] = []
    failed: list[str] = []

    def _on_ok() -> None:
        succeeded.append(True)

    def _on_fail(message: str) -> None:
        failed.append(message)

    thread.succeeded.connect(_on_ok)
    thread.failed.connect(_on_fail)
    # Leave the event loop as soon as the thread ends so the deadline below is
    # only a failure timeout rather than a fixed five-second wait.
    thread.finished.connect(qapp.exit)
    thread.start()
    # Bounded wait for either terminal signal.
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(qapp.exit)
    deadline.start(5000)
    qapp.exec()
    assert thread.wait(5000), "encoder thread did not finish within five seconds"
    return bool(succeeded), failed


class TestCineVideoEncodeThread:
    def test_success_emits_succeeded(self, qapp):
        thread, _ = _make_thread()
        with patch(
            "gui.dialogs.cine_export_encode_thread.encode_cine_video_from_png_paths"
        ) as enc:
            succeeded, failed = _run_and_wait(thread, qapp)
        enc.assert_called_once()
        args = enc.call_args.args
        assert list(args[0]) == [Path("a.png"), Path("b.png")]
        assert args[1] == "/tmp/out.mp4"
        assert args[2] == "mp4"
        assert args[3] == 10.0
        assert succeeded is True
        assert failed == []
        assert thread._paths == [Path("a.png"), Path("b.png")]
        assert thread._video_format == "mp4"
        assert thread._fps == 10.0

    def test_failure_emits_failed(self, qapp):
        thread, _ = _make_thread()
        with patch(
            "gui.dialogs.cine_export_encode_thread.encode_cine_video_from_png_paths",
            side_effect=RuntimeError("boom"),
        ):
            succeeded, failed = _run_and_wait(thread, qapp)
        assert succeeded is False
        assert failed and "boom" in failed[0]

    def test_cancel_after_encode_emits_failed(self, qapp):
        thread, cancel = _make_thread(cancel_set=True)
        with patch(
            "gui.dialogs.cine_export_encode_thread.encode_cine_video_from_png_paths"
        ) as enc:
            succeeded, failed = _run_and_wait(thread, qapp)
            enc.assert_called_once()
        assert succeeded is False
        assert failed and failed[0] == "Export cancelled."

    def test_init_coerces_paths_to_path(self):
        thread, _ = _make_thread(paths=["x.png"])
        assert thread._paths == [Path("x.png")]
        assert isinstance(thread._paths[0], Path)
