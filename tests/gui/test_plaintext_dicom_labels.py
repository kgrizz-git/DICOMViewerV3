"""DICOM-sourced QLabel text: plain text so tag-like strings are not rich HTML."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt


@pytest.mark.qt
def test_study_label_and_viewport_corners_use_plain_text(qapp) -> None:
    """Study navigator and overlay corners must not use Qt AutoText for DICOM strings."""
    from gui.overlay_manager import ViewportOverlayWidget
    from gui.series_navigator_view import StudyLabel

    s1 = "<b>desc</b>"
    study = StudyLabel(s1)
    inner = study.label
    assert inner.textFormat() == Qt.TextFormat.PlainText
    assert inner.text() == s1

    s2 = "<span>other</span>"
    study.set_text(s2)
    assert inner.textFormat() == Qt.TextFormat.PlainText
    assert inner.text() == s2

    overlay = ViewportOverlayWidget(parent=None)
    for label in overlay.corner_labels.values():
        assert label.textFormat() == Qt.TextFormat.PlainText

    img_markup = "<img src='x'>"
    for key in overlay.corner_labels:
        overlay.set_corner_text(key, img_markup, Qt.AlignmentFlag.AlignLeft)

    for label in overlay.corner_labels.values():
        assert label.textFormat() == Qt.TextFormat.PlainText
        assert label.text() == img_markup

    _ = qapp
