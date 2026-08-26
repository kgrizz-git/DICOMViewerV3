"""Focused tests for gui.image_viewer_item_context_menu."""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QGraphicsRectItem

import gui.image_viewer_item_context_menu as image_viewer_item_context_menu


class _FakeSignal:
    def __init__(self) -> None:
        self.calls = []

    def connect(self, callback):
        self.calls.append(callback)

    def emit(self, *args):
        self.calls.append(args)


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.triggered = _FakeSignal()
        self.checkable = False
        self.checked = False
        self.enabled = True
        self.visible = True
        self.tooltip = ""

    def setCheckable(self, value: bool) -> None:
        self.checkable = value

    def setChecked(self, value: bool) -> None:
        self.checked = value

    def setEnabled(self, value: bool) -> None:
        self.enabled = value

    def setVisible(self, value: bool) -> None:
        self.visible = value

    def setToolTip(self, value: str) -> None:
        self.tooltip = value


class _FakeMenu:
    instances: ClassVar[list[_FakeMenu]] = []

    def __init__(self, _parent=None) -> None:
        self.actions: list[_FakeAction] = []
        self.submenus: list[tuple[str, _FakeMenu]] = []
        self.enabled = True
        _FakeMenu.instances.append(self)

    def addAction(self, text: str) -> _FakeAction:
        action = _FakeAction(text)
        self.actions.append(action)
        return action

    def addSeparator(self):
        return None

    def addMenu(self, text: str):
        menu = _FakeMenu()
        self.submenus.append((text, menu))
        return menu

    def setEnabled(self, value: bool) -> None:
        self.enabled = value

    def exec(self, _pos):
        return None


def _require_submenu(menu: _FakeMenu, label: str) -> _FakeMenu:
    """Return the named submenu, or fail the test if it is missing.

    Uses ``next(..., None)`` so a missing label becomes an assertion failure
    instead of an uncaught ``StopIteration`` (DeepSource PTC-W0063).
    """
    found = next((submenu for name, submenu in menu.submenus if name == label), None)
    assert found is not None, f"missing submenu {label!r}"
    return found


def _event() -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(3, 4),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _make_viewer(**overrides):
    defaults = {
        "mapToScene": lambda p: p,
        "scene": SimpleNamespace(itemAt=MagicMock(return_value=None)),
        "transform": lambda: None,
        "roi_statistics_selection_changed": _FakeSignal(),
        "roi_delete_requested": _FakeSignal(),
        "measurement_delete_requested": _FakeSignal(),
        "text_annotation_delete_requested": _FakeSignal(),
        "arrow_annotation_delete_requested": _FakeSignal(),
        "crosshair_delete_requested": _FakeSignal(),
        "annotation_options_requested": _FakeSignal(),
        "roi_statistics_overlay_toggle_requested": _FakeSignal(),
        "_toggle_statistic": MagicMock(),
        "get_roi_from_item_callback": None,
        "delete_all_rois_callback": MagicMock(),
        "right_mouse_context_menu_shown": False,
        "right_mouse_drag_start_pos": None,
        "right_mouse_press_for_drag": _FakeSignal(),
        "image_item": object(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _install_fake_menu_patches(monkeypatch) -> None:
    # Patch QMenu only on the module under test; see the equivalent helper in
    # test_image_viewer_context_menu.py for why a global patch is unsafe.
    _FakeMenu.instances.clear()
    monkeypatch.setattr(image_viewer_item_context_menu, "QMenu", _FakeMenu)


def test_toggle_roi_statistic_adds_and_removes_entry() -> None:
    viewer = _make_viewer()
    roi = SimpleNamespace(visible_statistics={"mean"})

    image_viewer_item_context_menu.toggle_roi_statistic(viewer, roi, "std", True)
    image_viewer_item_context_menu.toggle_roi_statistic(viewer, roi, "mean", False)

    assert roi.visible_statistics == {"std"}
    assert viewer.roi_statistics_selection_changed.calls[-1] == (roi, {"std"})


@pytest.mark.qt
def test_handle_mouse_press_right_button_on_roi_builds_roi_menu(monkeypatch, qapp) -> None:
    _install_fake_menu_patches(monkeypatch)
    roi = SimpleNamespace(statistics_overlay_visible=True, visible_statistics={"mean", "count"})
    viewer = _make_viewer(
        scene=SimpleNamespace(itemAt=MagicMock(return_value=QGraphicsRectItem())),
        get_roi_from_item_callback=MagicMock(return_value=roi),
    )

    image_viewer_item_context_menu.handle_mouse_press_right_button(viewer, _event())

    assert viewer.right_mouse_context_menu_shown is True
    menu = _FakeMenu.instances[0]
    assert [action.text for action in menu.actions[:2]] == ["Delete ROI", "Delete all ROIs (D)"]
    stats_menu = _require_submenu(menu, "Statistics Overlay")
    stat_labels = [action.text for action in stats_menu.actions]
    assert "Show Statistics Overlay" in stat_labels
    assert "Show Mean" in stat_labels
    assert "Show Pixels" in stat_labels


@pytest.mark.qt
def test_handle_mouse_press_right_button_on_background_prepares_drag(monkeypatch, qapp) -> None:
    _install_fake_menu_patches(monkeypatch)
    viewer = _make_viewer()

    image_viewer_item_context_menu.handle_mouse_press_right_button(viewer, _event())

    assert viewer.right_mouse_context_menu_shown is False
    assert viewer.right_mouse_drag_start_pos == QPointF(3, 4)
    assert viewer.right_mouse_press_for_drag.calls[-1] == ()
