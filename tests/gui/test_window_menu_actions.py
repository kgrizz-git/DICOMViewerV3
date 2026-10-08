"""3D viewer window behavior: flags, keep-in-front setting, show/hide, reopen."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qt_widget_scope import widget_scope

from gui import volume_render_facade as facade_module
from gui import window_stacking
from gui.dialogs.volume_render_dialog import VolumeRenderDialog
from gui.main_window import MainWindow
from gui.volume_render_facade import VolumeRenderFacade
from utils.config_manager import ConfigManager

pytestmark = pytest.mark.qt


@pytest.fixture(autouse=True)
def _scope():
    with widget_scope():
        yield


class _Dlg(QWidget):
    """Real top-level window with the dialog surface the facade needs."""

    def __init__(self) -> None:
        super().__init__()
        self.refreshed = 0
        self.resize(200, 150)

    def refresh_stay_on_top(self) -> None:
        self.refreshed += 1


def _facade(*dialogs: QWidget, data: dict | None = None) -> VolumeRenderFacade:
    facade = VolumeRenderFacade(SimpleNamespace(main_window=None, subwindow_data=data or {}))
    facade._alive.extend(dialogs)
    return facade


@pytest.fixture(autouse=True)
def _no_active(monkeypatch):
    monkeypatch.setattr(facade_module.QApplication, "activeWindow", staticmethod(lambda: None))


def _stub_build(monkeypatch) -> None:
    monkeypatch.setattr(VolumeRenderDialog, "_start_build", lambda self: None)


def test_dialog_flags_include_minimize_and_maximize(qapp, monkeypatch) -> None:
    _stub_build(monkeypatch)
    dlg = VolumeRenderDialog([])
    flags = dlg.windowFlags()
    assert flags & Qt.WindowType.WindowMinimizeButtonHint
    assert flags & Qt.WindowType.WindowMaximizeButtonHint
    assert flags & Qt.WindowType.WindowCloseButtonHint
    assert dlg.parentWidget() is None
    dlg.deleteLater()


def test_dialog_stay_on_top_follows_setting_and_platform(qapp, monkeypatch) -> None:
    _stub_build(monkeypatch)
    cfg = SimpleNamespace(get_keep_3d_viewer_in_front=lambda: True)
    dlg = VolumeRenderDialog([], config_manager=cfg)
    monkeypatch.setattr(window_stacking, "_current_platform", lambda: "darwin")
    assert dlg._keep_in_front_enabled()
    cfg.get_keep_3d_viewer_in_front = lambda: False
    assert not dlg._keep_in_front_enabled()
    cfg.get_keep_3d_viewer_in_front = lambda: True
    monkeypatch.setattr(window_stacking, "_current_platform", lambda: "win32")
    assert not dlg._keep_in_front_enabled()
    dlg.deleteLater()


def test_setting_defaults_true_and_persists(qapp, tmp_path) -> None:
    cm = ConfigManager(config_dir=tmp_path / "config")
    assert cm.get_keep_3d_viewer_in_front() is True
    cm.set_keep_3d_viewer_in_front(False)
    assert ConfigManager(config_dir=tmp_path / "config").get_keep_3d_viewer_in_front() is False


def _window_and_app(tmp_path, facade):
    window = MainWindow(ConfigManager(config_dir=tmp_path / "config"))
    app = SimpleNamespace(
        main_window=window, _volume_render_facade=facade, get_focused_subwindow_index=lambda: 0
    )
    return window, app


def test_toggling_setting_persists_and_refreshes_live_dialogs(qapp, tmp_path) -> None:
    a, b = _Dlg(), _Dlg()
    facade = _facade(a, b)
    window, app = _window_and_app(tmp_path, facade)
    from gui.window_menu_actions import wire_3d_window_menu_actions

    wire_3d_window_menu_actions(app)
    action = window.keep_3d_viewer_in_front_action
    assert action.isCheckable()
    assert action.isChecked()
    action.trigger()
    assert window.config_manager.get_keep_3d_viewer_in_front() is False
    assert (a.refreshed, b.refreshed) == (1, 1)
    action.trigger()
    assert window.config_manager.get_keep_3d_viewer_in_front() is True
    assert (a.refreshed, b.refreshed) == (2, 2)


def test_show_action_enablement_and_checked_follow_dialogs(qapp, tmp_path) -> None:
    dlg = _Dlg()
    facade = _facade()
    window, app = _window_and_app(tmp_path, facade)
    from gui.window_menu_actions import wire_3d_window_menu_actions

    wire_3d_window_menu_actions(app)
    action = window.show_3d_viewer_action
    assert action.text() == "Show 3D Viewer"
    window.view_menu.aboutToShow.emit()
    assert not action.isEnabled()
    facade._alive.append(dlg)
    dlg.show()
    window.view_menu.aboutToShow.emit()
    assert action.isEnabled()
    assert action.isChecked()
    action.trigger()  # hide
    assert not dlg.isVisible()
    assert not action.isChecked()
    assert action.isEnabled()  # hidden window stays recoverable
    action.trigger()  # show again
    assert dlg.isVisible()
    assert action.isChecked()
    assert facade._alive == [dlg]
    dlg.close()


def test_toggle_keeps_same_dialog_and_never_builds(qapp) -> None:
    dlg = _Dlg()
    dlg.show()
    facade = _facade(dlg)
    with patch.object(facade_module, "VolumeRenderDialog") as ctor:
        assert facade.toggle_dialog_visibility() is False
        assert facade.toggle_dialog_visibility() is True
        ctor.assert_not_called()
    assert facade._alive == [dlg]
    assert dlg.isVisible()
    assert _facade().toggle_dialog_visibility() is None
    dlg.close()


def test_minimized_then_hidden_then_shown(qapp) -> None:
    dlg = _Dlg()
    dlg.show()
    dlg.showMinimized()
    if not dlg.isMinimized():
        pytest.skip("offscreen platform cannot minimize")
    facade = _facade(dlg)
    assert not facade.target_is_shown()
    dlg.hide()
    facade.restore_dialog(dlg)
    assert dlg.isVisible()
    assert not dlg.isMinimized()
    dlg.close()


def test_restore_keeps_maximized_state(qapp) -> None:
    dlg = _Dlg()
    dlg.showMaximized()
    if not dlg.isMaximized():
        pytest.skip("offscreen platform cannot maximize")
    dlg.hide()
    dlg.setWindowState(dlg.windowState() | Qt.WindowState.WindowMinimized)
    VolumeRenderFacade.restore_dialog(dlg)
    assert dlg.isVisible()
    assert not dlg.isMinimized()
    assert dlg.isMaximized()
    dlg.close()


def test_target_selection_with_hidden_dialogs(qapp) -> None:
    first, second, third = _Dlg(), _Dlg(), _Dlg()
    second.show()
    facade = _facade(first, second, third)
    assert facade._existing_dialogs() == [first, second, third]
    assert facade._live_dialogs() == [second]
    assert facade.target_dialog() is third  # most recently opened, hidden
    facade._last_active = first
    assert facade.target_dialog() is first
    second.close()


@pytest.mark.parametrize("minimize", [False, True])
def test_launch_reuses_hidden_or_minimized_dialog(qapp, minimize) -> None:
    dlg = _Dlg()
    dlg.show()
    if minimize:
        dlg.showMinimized()
        if not dlg.isMinimized():
            pytest.skip("offscreen platform cannot minimize")
    else:
        dlg.hide()
    app = SimpleNamespace(
        main_window=None,
        subwindow_data={0: {"study_uid": "s", "series_uid": "a"}},
        get_focused_subwindow_index=lambda: 0,
    )
    facade = VolumeRenderFacade(app)
    facade._alive.append(dlg)
    facade._open_dialogs["s|a"] = dlg
    with (
        patch.object(facade_module, "can_launch_3d_volume_render", return_value=(True, "")),
        patch.object(facade_module, "get_datasets_for_subwindow", return_value=["d"]),
        patch.object(facade_module, "VolumeRenderDialog") as ctor,
    ):
        facade.launch_3d_view(0)
        ctor.assert_not_called()
    assert dlg.isVisible()
    assert not dlg.isMinimized()
    assert facade._open_dialogs["s|a"] is dlg
    dlg.close()


def test_menu_builder_registers_actions(qapp, tmp_path) -> None:
    window = MainWindow(ConfigManager(config_dir=tmp_path / "config"))
    assert window.show_3d_viewer_action.isCheckable()
    assert not window.show_3d_viewer_action.isEnabled()
    assert "macOS" in window.keep_3d_viewer_in_front_action.toolTip()


def test_wiring_twice_does_not_double_toggle(qapp, tmp_path) -> None:
    dlg = _Dlg()
    dlg.show()
    facade = _facade(dlg)
    window, app = _window_and_app(tmp_path, facade)
    from gui.window_menu_actions import wire_3d_window_menu_actions

    wire_3d_window_menu_actions(app)
    wire_3d_window_menu_actions(app)
    window.view_menu.aboutToShow.emit()
    window.show_3d_viewer_action.trigger()
    assert not dlg.isVisible()  # a double toggle would have re-shown it
    window.keep_3d_viewer_in_front_action.trigger()
    assert dlg.refreshed == 1
    dlg.close()


def test_launch_reuse_marks_dialog_as_last_active(qapp) -> None:
    other, dlg = _Dlg(), _Dlg()
    dlg.hide()
    app = SimpleNamespace(
        main_window=None,
        subwindow_data={0: {"study_uid": "s", "series_uid": "a"}},
        get_focused_subwindow_index=lambda: 0,
    )
    facade = VolumeRenderFacade(app)
    facade._alive.extend([dlg, other])
    facade._open_dialogs["s|a"] = dlg
    facade._last_active = other
    with (
        patch.object(facade_module, "can_launch_3d_volume_render", return_value=(True, "")),
        patch.object(facade_module, "get_datasets_for_subwindow", return_value=["d"]),
    ):
        facade.launch_3d_view(0)
    assert facade._last_active is dlg
    dlg.close()
