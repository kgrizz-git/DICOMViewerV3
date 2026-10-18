"""Tests for CineExportDialog option defaults and build_options."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from gui.cine_video_export import FfmpegResolution
from gui.dialogs.cine_export_dialog import CineExportDialog


@pytest.mark.qt
def test_defaults_prefer_mp4_and_loop_bounds(qapp) -> None:
    dlg = CineExportDialog(
        None,
        default_fps=12.5,
        total_frames=10,
        loop_start=2,
        loop_end=7,
    )
    opts = dlg.build_options()
    assert opts.video_format == "MP4"
    assert opts.fps == pytest.approx(12.5)
    assert opts.use_cine_loop_bounds is True
    assert opts.loop_start_frame == 2
    assert opts.loop_end_frame == 7
    assert opts.include_overlays is False
    assert opts.export_scale == pytest.approx(1.0)


@pytest.mark.qt
def test_build_options_reflects_field_edits(qapp) -> None:
    dlg = CineExportDialog(
        None,
        default_fps=8.0,
        total_frames=5,
        loop_start=None,
        loop_end=None,
    )
    dlg._format_combo.setCurrentText("GIF")
    dlg._fps_spin.setValue(24.0)
    dlg._overlay_check.setChecked(True)
    dlg._resolution_combo.setCurrentIndex(2)  # 2x
    dlg._use_loop_check.setChecked(True)
    dlg._loop_start.setValue(1)
    dlg._loop_end.setValue(3)
    opts = dlg.build_options()
    assert opts.video_format == "GIF"
    assert opts.fps == pytest.approx(24.0)
    assert opts.include_overlays is True
    assert opts.export_scale == pytest.approx(2.0)
    assert opts.use_cine_loop_bounds is True
    assert opts.loop_start_frame == 1
    assert opts.loop_end_frame == 3


@pytest.mark.qt
def test_reject_leaves_dialog_rejected(qapp) -> None:
    dlg = CineExportDialog(
        None, default_fps=10.0, total_frames=3, loop_start=None, loop_end=None
    )
    dlg.reject()
    assert dlg.result() == int(dlg.DialogCode.Rejected)


@pytest.mark.qt
def test_dialog_disables_ffmpeg_formats_when_resolver_missing(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When FFmpeg is missing, GIF stays enabled and the dialog does not set env."""
    monkeypatch.delenv("IMAGEIO_FFMPEG_EXE", raising=False)
    missing = FfmpegResolution(path=None, source="missing")
    with patch(
        "gui.dialogs.cine_export_dialog.resolve_ffmpeg_exe",
        return_value=missing,
    ):
        dlg = CineExportDialog(
            None, default_fps=10.0, total_frames=3, loop_start=None, loop_end=None
        )
    model = dlg._format_combo.model()
    gif_item = model.item(0)
    assert gif_item is not None
    assert gif_item.flags() & Qt.ItemFlag.ItemIsEnabled
    for row, label in enumerate(("AVI", "MP4", "MPG"), start=1):
        item = model.item(row)
        assert item is not None
        assert item.text() == label
        assert not (item.flags() & Qt.ItemFlag.ItemIsEnabled)
    assert dlg.build_options().video_format == "GIF"
    assert "IMAGEIO_FFMPEG_EXE" not in os.environ


@pytest.mark.qt
def test_privacy_notice_is_visible(qapp) -> None:
    dlg = CineExportDialog(None, default_fps=10.0, total_frames=3, loop_start=None, loop_end=None)
    notice = dlg.findChild(QLabel, "cinePrivacyNotice")
    assert notice is not None
    assert "Review the rendered frames" in notice.text()
