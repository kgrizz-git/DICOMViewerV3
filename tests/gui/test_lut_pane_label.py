"""The pane LUT label: text, privacy, toggle, and refresh on repaint."""

from __future__ import annotations

import pytest

from core.lut_catalog import colormap_lut, gamma_lut, linear_lut
from core.lut_engine import LookUpTable
from gui.lut_pane_label import LutPaneLabel, lut_label_text

_SAVED = LookUpTable(name="Smith chest", source="custom", control_points=((0.0, 0.0), (1.0, 1.0)))


def test_label_text_names_only_a_non_default_lut() -> None:
    assert lut_label_text(None, False, False) == ""
    assert lut_label_text(linear_lut(), False, False) == ""
    assert lut_label_text(gamma_lut(2.2), False, False) == "LUT: Gamma"
    assert lut_label_text(colormap_lut("hot"), False, False) == "LUT: hot"
    # A custom curve that happens to be the identity is still named.
    assert lut_label_text(_SAVED, False, False) == "LUT: Smith chest"


def test_label_text_reports_from_dicom_with_or_without_a_lut() -> None:
    assert lut_label_text(linear_lut(), True, False) == "VOI LUT: DICOM"
    assert lut_label_text(gamma_lut(2.2), True, False) == "VOI LUT: DICOM  ·  LUT: Gamma"


def test_privacy_hides_user_names_but_not_builtins() -> None:
    assert lut_label_text(_SAVED, False, True) == "LUT: Custom"
    assert lut_label_text(colormap_lut("hot"), False, True) == "LUT: hot"


def _viewer(qapp, lut: LookUpTable, voi: bool = False):
    from gui.image_viewer import ImageViewer

    viewer = ImageViewer()
    viewer.resize(400, 300)
    viewer.current_series_lut = lambda: lut  # type: ignore[attr-defined]
    viewer.dicom_lut_state = lambda: (voi, voi)  # type: ignore[attr-defined]
    _ = qapp
    return viewer


@pytest.mark.qt
def test_label_follows_the_pane_and_the_toggle(qapp) -> None:
    viewer = _viewer(qapp, gamma_lut(2.2))
    settings = {"show": True, "privacy": False}
    pane_label = LutPaneLabel(
        viewer, show_label=lambda: settings["show"], privacy=lambda: settings["privacy"]
    )
    viewer.show()
    pane_label.refresh()
    assert pane_label.label.isVisible()
    assert pane_label.label.text() == "LUT: Gamma"
    assert pane_label.label.y() == 6
    settings["show"] = False
    LutPaneLabel.refresh_all()
    assert not pane_label.label.isVisible()
    settings["show"] = True
    viewer.current_series_lut = lambda: linear_lut()  # type: ignore[attr-defined]
    pane_label.refresh()
    assert not pane_label.label.isVisible()
    viewer.close()


@pytest.mark.qt
def test_a_viewport_repaint_refreshes_the_label(qapp) -> None:
    viewer = _viewer(qapp, linear_lut())
    pane_label = LutPaneLabel(viewer, show_label=lambda: True, privacy=lambda: False)
    viewer.show()
    from PySide6.QtGui import QPaintEvent
    from PySide6.QtWidgets import QApplication

    viewer.current_series_lut = lambda: colormap_lut("hot")  # type: ignore[attr-defined]
    viewport = viewer.viewport()
    QApplication.sendEvent(viewport, QPaintEvent(viewport.rect()))
    assert pane_label.label.text() == "LUT: hot"
    assert pane_label.label.isVisible()
    viewer.close()


@pytest.mark.qt
def test_view_menu_toggle_persists_and_refreshes(qapp, monkeypatch) -> None:
    from types import SimpleNamespace

    from PySide6.QtWidgets import QMenu

    from gui import lut_actions

    saved: list[bool] = []
    config = SimpleNamespace(get_show_lut_label=lambda: True, set_show_lut_label=saved.append)
    refreshed: list[bool] = []
    monkeypatch.setattr(LutPaneLabel, "refresh_all", classmethod(lambda cls: refreshed.append(True)))
    menu = QMenu()
    lut_actions.attach_view_lut_menu(menu, SimpleNamespace(config_manager=config))
    toggle = next(a for a in menu.actions() if a.text() == "Show LUT Label")
    assert toggle.isChecked()
    toggle.trigger()
    assert saved == [False]
    assert refreshed == [True]
    _ = qapp


def test_config_persists_the_toggle(tmp_path) -> None:
    from utils.config_manager import ConfigManager

    manager = ConfigManager(config_dir=tmp_path)
    assert manager.get_show_lut_label() is True
    manager.set_show_lut_label(False)
    assert ConfigManager(config_dir=tmp_path).get_show_lut_label() is False


@pytest.mark.qt
def test_label_does_not_claim_dicom_when_it_could_not_apply(qapp) -> None:
    viewer = _viewer(qapp, linear_lut())
    viewer.dicom_lut_state = lambda: (False, True)  # type: ignore[attr-defined]
    pane_label = LutPaneLabel(viewer, show_label=lambda: True, privacy=lambda: False)
    assert pane_label.current_text() == ""
    viewer.dicom_lut_state = lambda: (True, True)  # type: ignore[attr-defined]
    assert pane_label.current_text() == "VOI LUT: DICOM"
