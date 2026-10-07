"""File → Save 3D View…: menu action wiring and facade target selection."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtWidgets import QMessageBox
from qt_widget_scope import widget_scope

from gui import app_signal_wiring
from gui import volume_render_facade as facade_module
from gui.main_window import MainWindow
from gui.volume_render_facade import VolumeRenderFacade
from utils.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def _destroy_leaked_windows():
    with widget_scope():
        yield


class _Dialog:
    def __init__(self, *, visible: bool = True, ready: bool = True) -> None:
        self.visible = visible
        self.ready = ready
        self.saved = 0

    def isVisible(self) -> bool:
        return self.visible

    def raise_(self) -> None:
        pass

    def activateWindow(self) -> None:
        pass

    def can_save_image(self) -> bool:
        return self.ready

    def save_image(self) -> bool:
        self.saved += 1
        return True


def _facade(*dialogs: _Dialog, subwindow_data: dict | None = None) -> VolumeRenderFacade:
    app = SimpleNamespace(main_window=None, subwindow_data=subwindow_data or {})
    facade = VolumeRenderFacade(app)
    facade._alive.extend(dialogs)
    return facade


def _no_active_window(monkeypatch) -> None:
    monkeypatch.setattr(facade_module.QApplication, "activeWindow", staticmethod(lambda: None))


def test_has_open_dialog_ignores_hidden_dialogs() -> None:
    assert not _facade().has_open_dialog()
    assert not _facade(_Dialog(visible=False)).has_open_dialog()
    assert _facade(_Dialog()).has_open_dialog()


def test_target_prefers_focused_series_then_most_recent(monkeypatch) -> None:
    _no_active_window(monkeypatch)
    first, second = _Dialog(), _Dialog()
    facade = _facade(first, second, subwindow_data={0: {"study_uid": "s", "series_uid": "a"}})
    facade._open_dialogs["s|a"] = first
    assert facade.target_dialog(0) is first
    assert facade.target_dialog(1) is second
    assert facade.target_dialog(None) is second


def test_target_prefers_the_active_3d_window(monkeypatch) -> None:
    first, second = _Dialog(), _Dialog()
    monkeypatch.setattr(facade_module.QApplication, "activeWindow", staticmethod(lambda: first))
    assert _facade(first, second).target_dialog(None) is first


def test_save_without_3d_window_informs_and_saves_nothing(monkeypatch) -> None:
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, text: shown.append(text))
    assert _facade().save_3d_view() is False
    assert shown and "Open a 3D view first" in shown[0]


def test_save_before_first_frame_informs_and_saves_nothing(monkeypatch) -> None:
    _no_active_window(monkeypatch)
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, text: shown.append(text))
    dialog = _Dialog(ready=False)
    assert _facade(dialog).save_3d_view() is False
    assert dialog.saved == 0
    assert shown and "not ready" in shown[0]


def test_save_runs_the_dialog_save_flow(monkeypatch) -> None:
    _no_active_window(monkeypatch)
    dialog = _Dialog()
    assert _facade(dialog).save_3d_view() is True
    assert dialog.saved == 1


def test_file_menu_action_enables_only_with_an_open_3d_window(qapp, tmp_path) -> None:
    window = MainWindow(ConfigManager(config_dir=tmp_path / "config"))
    action = window.save_3d_view_action
    assert action.text() == "Save 3D View…"
    assert not action.isEnabled()
    facade = _facade()
    calls: list[Any] = []
    facade.save_3d_view = lambda idx=None: calls.append(idx) or True  # type: ignore[method-assign]
    app = SimpleNamespace(
        main_window=window, _volume_render_facade=facade, get_focused_subwindow_index=lambda: 2
    )
    app_signal_wiring._wire_save_3d_view_action(app)
    window.file_menu.aboutToShow.emit()
    assert not action.isEnabled()
    facade._alive.append(_Dialog())
    window.file_menu.aboutToShow.emit()
    assert action.isEnabled()
    action.trigger()
    assert calls == [2]
