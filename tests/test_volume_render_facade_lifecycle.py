from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from gui.dialogs.volume_render_dialog import VolumeRenderDialog
from gui.volume_render_facade import VolumeRenderFacade


class _TrackedDialog:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _UntrackedVolumeRenderDialog(VolumeRenderDialog):
    def __init__(self) -> None:
        QDialog.__init__(self, None)
        self.closed = False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

    def closeEvent(self, event: Any) -> None:
        self.closed = True
        event.accept()


@pytest.mark.qt
def test_close_all_dialogs_closes_tracked_dialogs(qapp) -> None:
    facade = VolumeRenderFacade(SimpleNamespace())
    tracked = _TrackedDialog()
    facade._alive.append(tracked)
    facade._open_dialogs["study|series"] = tracked

    facade.close_all_dialogs()

    assert tracked.closed is True
    assert facade._alive == []
    assert facade._open_dialogs == {}


@pytest.mark.qt
def test_close_all_dialogs_sweeps_untracked_top_level_3d_dialogs(qapp) -> None:
    facade = VolumeRenderFacade(SimpleNamespace())
    dialog = _UntrackedVolumeRenderDialog()
    dialog.show()
    qapp.processEvents()

    try:
        facade.close_all_dialogs()
        qapp.processEvents()

        assert dialog.closed is True
        assert dialog.isVisible() is False
    finally:
        if dialog.isVisible():
            dialog.close()
        qapp.processEvents()
