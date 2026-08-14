"""Round-4 MeasurementTool tests: lifecycle and slice management."""
# ruff: noqa: F401

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (
    QGraphicsScene,
)

from tools.angle_measurement_items import AngleMeasurementItem
from tools.measurement_items import MeasurementItem
from tools.measurement_tool import MeasurementTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scene() -> QGraphicsScene:
    return QGraphicsScene()


def _finish_distance(tool: MeasurementTool, scene: QGraphicsScene, p1: QPointF, p2: QPointF) -> MeasurementItem:
    tool.start_measurement(p1)
    tool.update_measurement(p2, scene)
    item = tool.finish_measurement(scene)
    assert item is not None
    return item


def _place_angle(tool: MeasurementTool, scene: QGraphicsScene, p1: QPointF, p2: QPointF, p3: QPointF) -> AngleMeasurementItem:
    tool.handle_angle_click(p1, scene)
    tool.handle_angle_click(p2, scene)
    item = tool.handle_angle_click(p3, scene)
    assert item is not None
    return item


# ---------------------------------------------------------------------------
# get_debug_summary
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestGetDebugSummary:
    def test_empty_returns_stored_zero(self, qapp) -> None:
        tool = MeasurementTool()
        assert tool.get_debug_summary() == "stored=0"

    def test_non_empty_without_scene(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.set_current_slice("S1", "SE1", 0)
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(10, 0))
        summary = tool.get_debug_summary()
        assert "count=1" in summary
        assert "attached" not in summary

    def test_non_empty_with_scene(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.set_current_slice("S1", "SE1", 0)
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(10, 0))
        summary = tool.get_debug_summary(scene)
        assert "attached=1" in summary

    def test_non_attached_measurement(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        other_scene = _make_scene()
        tool.set_current_slice("S1", "SE1", 0)
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(10, 0))
        summary = tool.get_debug_summary(other_scene)
        assert "attached=0" in summary


# ---------------------------------------------------------------------------
# set_pixel_spacing propagates to existing measurements
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestSetPixelSpacingUpdate:
    def test_updates_existing_distance_label(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(10, 0))
        item = tool.get_measurements_for_slice("S", "SE", 0)[0]
        assert "pixels" in item.text_item.toPlainText()

        tool.set_pixel_spacing((1.0, 1.0))
        assert item.pixel_spacing == (1.0, 1.0)
        assert "mm" in item.text_item.toPlainText()

    def test_no_measurements_does_not_crash(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((0.5, 0.5))
        assert tool.pixel_spacing == (0.5, 0.5)


# ---------------------------------------------------------------------------
# update_measurement early-return when not measuring
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestUpdateMeasurementGuard:
    def test_early_return_when_not_measuring(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.update_measurement(QPointF(5, 5), scene)
        assert len(scene.items()) == 0

    def test_multiple_updates_replace_preview(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.start_measurement(QPointF(0, 0))
        tool.update_measurement(QPointF(10, 0), scene)
        tool.update_measurement(QPointF(20, 0), scene)
        # Two items: line + text
        assert len(scene.items()) == 2
        tool.cancel_measurement(scene)


# ---------------------------------------------------------------------------
# finish_measurement guard branches
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestFinishMeasurementGuards:
    def test_returns_none_when_not_measuring(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        assert tool.finish_measurement(scene) is None

    def test_returns_none_when_no_start_point(self, qapp) -> None:
        tool = MeasurementTool()
        tool.measuring = True
        scene = _make_scene()
        assert tool.finish_measurement(scene) is None

    def test_returns_none_when_no_line_item(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.start_measurement(QPointF(0, 0))
        # Skip update_measurement so line/text are None
        assert tool.finish_measurement(scene) is None
        assert not tool.measuring


# ---------------------------------------------------------------------------
# finish_measurement with/without pixel spacing
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestFinishMeasurementDistance:
    def test_no_pixel_spacing_uses_pixels(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(30, 40))
        assert "pixels" in item.text_item.toPlainText()
        # 3-4-5 triangle: 50.0 pixels
        assert "50.0" in item.text_item.toPlainText()

    def test_with_pixel_spacing_uses_mm(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(10, 0))
        assert "mm" in item.text_item.toPlainText()

    def test_large_distance_format(self, qapp) -> None:
        """distance >= 10 mm uses one decimal place."""
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(100, 0))
        text = item.text_item.toPlainText()
        assert "100.0 mm" in text

    def test_small_distance_format(self, qapp) -> None:
        """distance < 10 mm uses two decimal places."""
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(3, 4))
        text = item.text_item.toPlainText()
        assert "5.00 mm" in text


# ---------------------------------------------------------------------------
# finish_measurement stores in measurements dict
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestFinishMeasurementStorage:
    def test_stored_under_correct_key(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 7)
        scene = _make_scene()
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        stored = tool.get_measurements_for_slice("S", "SE", 7)
        assert item in stored
        assert len(stored) == 1

    def test_creates_key_if_missing(self, qapp) -> None:
        tool = MeasurementTool()
        assert ("S", "SE", 0) not in tool.measurements
        scene = _make_scene()
        tool.set_current_slice("S", "SE", 0)
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        assert ("S", "SE", 0) in tool.measurements

    def test_multiple_measurements_same_slice(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        _finish_distance(tool, scene, QPointF(10, 10), QPointF(20, 20))
        assert len(tool.get_measurements_for_slice("S", "SE", 0)) == 2


# ---------------------------------------------------------------------------
# cancel_measurement
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestCancelMeasurement:
    def test_removes_preview_items(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.start_measurement(QPointF(0, 0))
        tool.update_measurement(QPointF(5, 5), scene)
        assert len(scene.items()) == 2
        tool.cancel_measurement(scene)
        assert len(scene.items()) == 0

    def test_resets_state(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.start_measurement(QPointF(0, 0))
        tool.update_measurement(QPointF(5, 5), scene)
        tool.cancel_measurement(scene)
        assert not tool.measuring
        assert tool.start_point is None
        assert tool.current_end_point is None
        assert tool.current_line_item is None
        assert tool.current_text_item is None

    def test_cancel_without_update(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.start_measurement(QPointF(0, 0))
        tool.cancel_measurement(scene)
        assert not tool.measuring


# ---------------------------------------------------------------------------
# clear_measurements (all slices)
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestClearAllMeasurements:
    def test_removes_all_items_and_keys(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        tool.set_current_slice("S", "SE", 1)
        _finish_distance(tool, scene, QPointF(10, 10), QPointF(15, 10))
        assert len(tool.measurements) == 2
        tool.clear_measurements(scene)
        assert len(tool.measurements) == 0
        # Only measurement items remain in scene if any; no text/handles
        measurement_items = [i for i in scene.items() if isinstance(i, (MeasurementItem, AngleMeasurementItem))]
        assert len(measurement_items) == 0

    def test_clear_empty_dict(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.clear_measurements(scene)
        assert len(tool.measurements) == 0


# ---------------------------------------------------------------------------
# delete_measurement
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestDeleteMeasurement:
    def test_removes_from_scene_and_dict(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(10, 0))
        assert item.scene() is scene
        tool.delete_measurement(item, scene)
        assert item.scene() is None
        assert tool.get_measurements_for_slice("S", "SE", 0) == []

    def test_deletes_only_target(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item_a = _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        item_b = _finish_distance(tool, scene, QPointF(10, 10), QPointF(15, 10))
        tool.delete_measurement(item_a, scene)
        assert item_a.scene() is None
        assert item_b.scene() is scene
        remaining = tool.get_measurements_for_slice("S", "SE", 0)
        assert item_b in remaining
        assert item_a not in remaining


# ---------------------------------------------------------------------------
# clear_measurements_from_other_slices
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestClearMeasurementsFromOtherSlices:
    def test_removes_other_slice_items(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.set_pixel_spacing((1.0, 1.0))
        # Add measurement to slice 0
        tool.set_current_slice("S", "SE", 0)
        item0 = _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        # Add measurement to slice 1
        tool.set_current_slice("S", "SE", 1)
        item1 = _finish_distance(tool, scene, QPointF(10, 10), QPointF(15, 10))
        # Clear measurements not belonging to slice 1
        tool.clear_measurements_from_other_slices("S", "SE", 1, scene)
        assert item0.scene() is None
        assert item1.scene() is scene

    def test_keeps_current_slice(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        tool.clear_measurements_from_other_slices("S", "SE", 0, scene)
        assert item.scene() is scene


# ---------------------------------------------------------------------------
# display_measurements_for_slice
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestDisplayMeasurementsForSlice:
    def test_adds_items_to_scene(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        item = tool.get_measurements_for_slice("S", "SE", 0)[0]
        # Remove from scene to simulate needing re-display
        if item.text_item is not None and item.text_item.scene() is scene:
            scene.removeItem(item.text_item)
        scene.removeItem(item)
        assert item.scene() is None
        tool.display_measurements_for_slice("S", "SE", 0, scene)
        assert item.scene() is scene

    def test_already_in_scene(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        # Should not crash even if already in scene
        tool.display_measurements_for_slice("S", "SE", 0, scene)
        item = tool.get_measurements_for_slice("S", "SE", 0)[0]
        assert item.scene() is scene

    def test_empty_slice(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.display_measurements_for_slice("S", "SE", 99, scene)


# ---------------------------------------------------------------------------
# clear_slice_measurements
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestClearSliceMeasurements:
    def test_removes_only_target_slice(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        item0 = _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        tool.set_current_slice("S", "SE", 1)
        item1 = _finish_distance(tool, scene, QPointF(10, 10), QPointF(15, 10))
        tool.clear_slice_measurements("S", "SE", 0, scene)
        assert item0.scene() is None
        assert item1.scene() is scene
        assert ("S", "SE", 0) not in tool.measurements
        assert ("S", "SE", 1) in tool.measurements

    def test_clear_nonexistent_key(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.clear_slice_measurements("S", "SE", 99, scene)


# ---------------------------------------------------------------------------
# get_measurements_for_slice
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestGetMeasurementsForSlice:
    def test_returns_empty_for_missing_key(self, qapp) -> None:
        tool = MeasurementTool()
        assert tool.get_measurements_for_slice("S", "SE", 0) == []


# ---------------------------------------------------------------------------
# set_current_slice
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestSetCurrentSlice:
    def test_creates_key(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 5)
        assert ("S", "SE", 5) in tool.measurements
        assert tool.measurements[("S", "SE", 5)] == []

    def test_idempotent(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 5)
        tool.set_current_slice("S", "SE", 5)
        assert ("S", "SE", 5) in tool.measurements
