"""Behavioral tests for the current-slice ROI list panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt

from gui.roi_list_panel import ROIListPanel


class _FakeGraphicsItem:
    def __init__(self, scene: object | None) -> None:
        self._scene = scene

    def scene(self) -> object | None:
        return self._scene


@dataclass
class _FakeROI:
    shape_type: str
    item: _FakeGraphicsItem
    statistics_overlay_visible: bool = False
    visible_statistics: list[str] = field(default_factory=list)


class _FakeROIManager:
    def __init__(self, rois: list[_FakeROI]) -> None:
        self.rois = rois
        self.selected: list[_FakeROI] = []
        self.deleted: list[tuple[_FakeROI, object]] = []
        self.requested_slices: list[tuple[str, str, int]] = []

    def get_rois_for_slice(self, study: str, series: str, instance: int) -> list[_FakeROI]:
        self.requested_slices.append((study, series, instance))
        return self.rois

    def select_roi(self, roi: _FakeROI) -> None:
        self.selected.append(roi)

    def delete_roi(self, roi: _FakeROI, scene: object) -> None:
        self.deleted.append((roi, scene))
        self.rois.remove(roi)


def _roi(shape: str, scene: object | None = None) -> _FakeROI:
    return _FakeROI(shape, _FakeGraphicsItem(scene if scene is not None else object()))


@pytest.mark.qt
def test_update_populates_slice_restores_roi_selection_and_button_states(qapp) -> None:
    first = _roi("rectangle")
    second = _roi("ellipse")
    manager = _FakeROIManager([first, second])
    panel = ROIListPanel()

    panel.update_roi_list("study", "series", 4, manager)

    assert panel.roi_manager is manager
    assert manager.requested_slices == [("study", "series", 4)]
    assert [panel.roi_list.item(i).text() for i in range(panel.roi_list.count())] == [
        "ROI 1 (rectangle)",
        "ROI 2 (ellipse)",
    ]
    assert not panel.delete_button.isEnabled()
    assert panel.delete_all_button.isEnabled()

    panel.roi_list.setCurrentRow(1)
    manager.selected.clear()
    panel.update_roi_list("study", "series", 4)

    assert panel.roi_list.currentItem().data(Qt.ItemDataRole.UserRole) is second
    assert panel.delete_button.isEnabled()
    assert manager.selected == [second]


@pytest.mark.qt
def test_selection_and_double_click_select_manager_roi_and_emit_signal(qapp) -> None:
    roi = _roi("rectangle")
    manager = _FakeROIManager([roi])
    panel = ROIListPanel()
    selected: list[_FakeROI] = []
    panel.roi_selected.connect(selected.append)
    panel.update_roi_list("study", "series", 1, manager)

    panel.roi_list.setCurrentRow(0)

    assert manager.selected == [roi]
    assert selected == [roi]
    assert panel.delete_button.isEnabled()

    panel._on_item_double_clicked(panel.roi_list.item(0))

    assert manager.selected == [roi, roi]
    assert selected == [roi, roi]


@pytest.mark.qt
def test_select_roi_in_list_selects_matching_roi_and_none_clears_it(qapp) -> None:
    first = _roi("rectangle")
    second = _roi("ellipse")
    manager = _FakeROIManager([first, second])
    panel = ROIListPanel()
    panel.update_roi_list("study", "series", 1, manager)

    panel.select_roi_in_list(second)

    assert panel.roi_list.currentItem().data(Qt.ItemDataRole.UserRole) is second
    assert manager.selected == [second]

    panel.select_roi_in_list(None)

    assert panel.roi_list.currentItem() is None
    assert not panel.delete_button.isEnabled()
    assert panel.delete_all_button.isEnabled()


@pytest.mark.qt
def test_delete_selected_uses_manager_emits_and_repopulates_list(qapp) -> None:
    roi = _roi("rectangle")
    manager = _FakeROIManager([roi])
    panel = ROIListPanel()
    deleted: list[_FakeROI] = []
    panel.roi_deleted.connect(deleted.append)
    panel.update_roi_list("study", "series", 2, manager)
    panel.roi_list.setCurrentRow(0)

    panel._delete_selected_roi()

    assert manager.deleted == [(roi, roi.item.scene())]
    assert deleted == [roi]
    assert panel.roi_list.count() == 0
    assert not panel.delete_button.isEnabled()
    assert not panel.delete_all_button.isEnabled()


@pytest.mark.qt
def test_context_delete_uses_callback_without_default_manager_delete(qapp) -> None:
    roi = _roi("ellipse")
    manager = _FakeROIManager([roi])
    panel = ROIListPanel()
    callback = MagicMock()
    panel.roi_delete_callback = callback
    panel.set_roi_manager(manager)

    panel._handle_delete_roi(roi)

    callback.assert_called_once_with(roi)
    assert manager.deleted == []


@pytest.mark.qt
def test_context_delete_falls_back_to_manager_and_emits(qapp) -> None:
    roi = _roi("ellipse")
    manager = _FakeROIManager([roi])
    panel = ROIListPanel()
    deleted: list[_FakeROI] = []
    panel.roi_deleted.connect(deleted.append)
    panel.update_roi_list("study", "series", 3, manager)

    panel._handle_delete_roi(roi)

    assert manager.deleted == [(roi, roi.item.scene())]
    assert deleted == [roi]
    assert panel.roi_list.count() == 0


@pytest.mark.qt
def test_delete_all_signal_and_context_callbacks_are_forwarded(qapp) -> None:
    panel = ROIListPanel()
    delete_all_requested = MagicMock()
    annotation_options = MagicMock()
    panel.delete_all_requested.connect(delete_all_requested)
    panel.annotation_options_callback = annotation_options

    panel._delete_all_rois()
    panel._handle_annotation_options()

    delete_all_requested.assert_called_once_with()
    annotation_options.assert_called_once_with()


@pytest.mark.qt
def test_statistics_callbacks_receive_selected_roi_and_requested_state(qapp) -> None:
    roi = _roi("rectangle")
    panel = ROIListPanel()
    overlay_callback = MagicMock()
    statistic_callback = MagicMock()
    panel.roi_statistics_overlay_toggle_callback = overlay_callback
    panel.roi_statistics_selection_callback = statistic_callback

    panel._handle_statistics_overlay_toggle(roi, True)
    panel._handle_statistic_toggle(roi, "mean", False)

    overlay_callback.assert_called_once_with(roi, True)
    statistic_callback.assert_called_once_with(roi, "mean", False)
