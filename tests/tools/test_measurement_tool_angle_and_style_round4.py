"""Round-4 MeasurementTool tests: angle, styling, and multi-slice behavior."""
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
class TestAngleToolStateMachine:
    def test_three_click_creates_angle(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        assert isinstance(item, AngleMeasurementItem)
        assert ("S", "SE", 0) in tool.measurements

    def test_angle_phase_resets_after_commit(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        assert tool.angle_phase == 0
        assert tool.angle_p1 is None
        assert tool.angle_p2 is None

    def test_phase_zero_returns_none(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        result = tool.handle_angle_click(QPointF(0, 0), scene)
        assert result is None
        assert tool.angle_phase == 1

    def test_phase_one_returns_none(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)
        result = tool.handle_angle_click(QPointF(0, 50), scene)
        assert result is None
        assert tool.angle_phase == 2

    def test_incomplete_angle_returns_none(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)
        assert tool.angle_phase == 1


# ---------------------------------------------------------------------------
# cancel_angle_in_progress
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestCancelAngleInProgress:
    def test_resets_phase_and_points(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)
        tool.handle_angle_click(QPointF(0, 50), scene)
        assert tool.angle_phase == 2
        tool.cancel_angle_in_progress(scene)
        assert tool.angle_phase == 0
        assert tool.angle_p1 is None
        assert tool.angle_p2 is None

    def test_removes_preview_items(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)
        # Trigger preview in phase 1
        tool.update_angle_preview(QPointF(10, 10), scene)
        assert tool.angle_preview_line1 is not None
        tool.cancel_angle_in_progress(scene)
        assert tool.angle_preview_line1 is None
        assert tool.angle_preview_line2 is None
        assert tool.angle_preview_text is None

    def test_cancel_when_nothing_in_progress(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.cancel_angle_in_progress(scene)
        assert tool.angle_phase == 0


# ---------------------------------------------------------------------------
# update_angle_preview
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestUpdateAnglePreview:
    def test_phase_zero_noop(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.update_angle_preview(QPointF(10, 10), scene)
        assert tool.angle_preview_line1 is None

    def test_phase_one_creates_line1(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)  # phase 1
        tool.update_angle_preview(QPointF(10, 10), scene)
        assert tool.angle_preview_line1 is not None
        assert tool.angle_preview_line1.scene() is scene
        # Phase 1 should not have line2 or text
        assert tool.angle_preview_line2 is None

    def test_phase_two_creates_both_lines_and_text(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)   # phase 1
        tool.handle_angle_click(QPointF(0, 50), scene)   # phase 2
        tool.update_angle_preview(QPointF(50, 50), scene)
        assert tool.angle_preview_line1 is not None
        assert tool.angle_preview_line2 is not None
        assert tool.angle_preview_text is not None
        assert tool.angle_preview_line1.scene() is scene
        assert tool.angle_preview_line2.scene() is scene
        assert tool.angle_preview_text.scene() is scene

    def test_phase_two_updates_existing_items(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)
        tool.handle_angle_click(QPointF(0, 50), scene)
        tool.update_angle_preview(QPointF(50, 50), scene)
        line1_ref = tool.angle_preview_line1
        text_ref = tool.angle_preview_text
        tool.update_angle_preview(QPointF(60, 60), scene)
        assert tool.angle_preview_line1 is line1_ref
        assert tool.angle_preview_text is text_ref

    def test_phase_one_clears_stale_line2_and_text(self, qapp) -> None:
        """If preview items from phase 2 exist, phase 1 update removes them."""
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)
        tool.handle_angle_click(QPointF(0, 50), scene)
        tool.update_angle_preview(QPointF(50, 50), scene)
        assert tool.angle_preview_line2 is not None
        # Now reset to phase 1 and update
        tool.angle_phase = 1
        tool.angle_p2 = None
        tool.update_angle_preview(QPointF(20, 20), scene)
        assert tool.angle_preview_line2 is None
        assert tool.angle_preview_text is None


# ---------------------------------------------------------------------------
# _clear_angle_preview (private but exercised through cancel and commit)
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestClearAnglePreview:
    def test_clears_items_in_scene(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)
        tool.handle_angle_click(QPointF(0, 50), scene)
        tool.update_angle_preview(QPointF(50, 50), scene)
        tool._clear_angle_preview(scene)
        assert tool.angle_preview_line1 is None
        assert tool.angle_preview_line2 is None
        assert tool.angle_preview_text is None

    def test_clear_when_items_not_in_scene(self, qapp) -> None:
        tool = MeasurementTool()
        scene = _make_scene()
        # No items created; clearing should be a no-op
        tool._clear_angle_preview(scene)
        assert tool.angle_preview_line1 is None


# ---------------------------------------------------------------------------
# _measurement_pen
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestMeasurementPen:
    def test_default_pen(self, qapp) -> None:
        tool = MeasurementTool()
        pen = tool._measurement_pen()
        assert pen.width() == 2
        assert pen.color().red() == 0
        assert pen.color().green() == 255
        assert pen.color().blue() == 0
        assert pen.isCosmetic()

    def test_pen_with_config(self, qapp) -> None:
        config = MagicMock()
        config.get_measurement_line_thickness.return_value = 3
        config.get_measurement_line_color.return_value = (255, 0, 0)
        tool = MeasurementTool(config_manager=config)
        pen = tool._measurement_pen()
        assert pen.width() == 3
        assert pen.color().red() == 255
        assert pen.color().green() == 0
        assert pen.color().blue() == 0


# ---------------------------------------------------------------------------
# update_all_measurement_text_offsets
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestUpdateAllMeasurementTextOffsets:
    def test_calls_update_text_offset_for_zoom(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        # Item has update_text_offset_for_zoom method; just verify no crash
        tool.update_all_measurement_text_offsets()

    def test_empty_measurements(self, qapp) -> None:
        tool = MeasurementTool()
        tool.update_all_measurement_text_offsets()


# ---------------------------------------------------------------------------
# update_all_measurement_styles
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestUpdateAllMeasurementStyles:
    def test_none_config_is_noop(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        tool.update_all_measurement_styles(None)

    def test_updates_distance_measurement_style(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        config = MagicMock()
        config.get_measurement_line_thickness.return_value = 4
        config.get_measurement_line_color.return_value = (255, 0, 0)
        config.get_measurement_font_size.return_value = 14
        config.get_measurement_font_color.return_value = (0, 0, 255)
        config.get_measurement_font_family.return_value = "Arial"
        config.get_measurement_font_variant.return_value = "Regular"
        tool.update_all_measurement_styles(config)
        assert item.line_item.pen().width() == 4
        assert item.line_item.pen().color().red() == 255

    def test_updates_angle_measurement_style(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        angle = _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        config = MagicMock()
        config.get_measurement_line_thickness.return_value = 5
        config.get_measurement_line_color.return_value = (128, 128, 128)
        config.get_measurement_font_size.return_value = 12
        config.get_measurement_font_color.return_value = (64, 64, 64)
        config.get_measurement_font_family.return_value = "Helvetica"
        config.get_measurement_font_variant.return_value = "Bold"
        tool.update_all_measurement_styles(config)
        assert angle.line1_item.pen().width() == 5
        assert angle.line2_item.pen().width() == 5

    def test_angle_handle_none_h0_h1_h2(self, qapp) -> None:
        """AngleMeasurementItem always has h0/h1/h2, but exercise the guard."""
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        angle = _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        angle.hide_handles()
        config = MagicMock()
        config.get_measurement_line_thickness.return_value = 2
        config.get_measurement_line_color.return_value = (0, 255, 0)
        config.get_measurement_font_size.return_value = 10
        config.get_measurement_font_color.return_value = (0, 255, 0)
        config.get_measurement_font_family.return_value = "Arial"
        config.get_measurement_font_variant.return_value = "Regular"
        # Should not crash even with handles removed
        tool.update_all_measurement_styles(config)


# ---------------------------------------------------------------------------
# Multi-slice interaction
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestMultiSliceInteraction:
    def test_switching_slices_shows_correct_items(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        scene = _make_scene()

        tool.set_current_slice("S", "SE", 0)
        item0 = _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))

        tool.set_current_slice("S", "SE", 1)
        item1 = _finish_distance(tool, scene, QPointF(10, 10), QPointF(15, 10))

        # Both in scene initially
        assert item0.scene() is scene
        assert item1.scene() is scene

        # Clear other slices - only slice 0 should remain
        tool.clear_measurements_from_other_slices("S", "SE", 0, scene)
        assert tool.get_measurements_for_slice("S", "SE", 0) == [item0]
        assert len(tool.get_measurements_for_slice("S", "SE", 1)) == 1

    def test_delete_from_middle_slice(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        scene = _make_scene()

        tool.set_current_slice("S", "SE", 0)
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        tool.set_current_slice("S", "SE", 1)
        i1 = _finish_distance(tool, scene, QPointF(10, 10), QPointF(15, 10))
        tool.set_current_slice("S", "SE", 2)
        _finish_distance(tool, scene, QPointF(20, 20), QPointF(25, 20))

        tool.delete_measurement(i1, scene)
        assert i1.scene() is None
        assert len(tool.get_measurements_for_slice("S", "SE", 0)) == 1
        assert len(tool.get_measurements_for_slice("S", "SE", 1)) == 0
        assert len(tool.get_measurements_for_slice("S", "SE", 2)) == 1

    def test_clear_all_then_reuse(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        scene = _make_scene()

        tool.set_current_slice("S", "SE", 0)
        _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        tool.clear_measurements(scene)
        assert len(tool.measurements) == 0

        # Can reuse tool cleanly
        tool.set_current_slice("S", "SE", 0)
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(10, 0))
        assert item.scene() is scene


# ---------------------------------------------------------------------------
# Angle measurement lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestAngleMeasurementLifecycle:
    def test_angle_gets_stored(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 3)
        scene = _make_scene()
        item = _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        stored = tool.get_measurements_for_slice("S", "SE", 3)
        assert item in stored

    def test_angle_can_be_deleted(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        tool.delete_measurement(item, scene)
        assert item.scene() is None
        assert tool.get_measurements_for_slice("S", "SE", 0) == []

    def test_angle_cancel_does_not_affect_committed(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        committed = _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        # Start a new angle then cancel
        tool.handle_angle_click(QPointF(100, 100), scene)
        tool.cancel_angle_in_progress(scene)
        # Committed angle is untouched
        assert committed.scene() is scene
        assert len(tool.get_measurements_for_slice("S", "SE", 0)) == 1

    def test_angle_clear_all(self, qapp) -> None:
        tool = MeasurementTool()
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        _finish_distance(tool, scene, QPointF(10, 10), QPointF(15, 10))
        tool.clear_measurements(scene)
        assert len(tool.measurements) == 0
        measurement_items = [i for i in scene.items() if isinstance(i, (MeasurementItem, AngleMeasurementItem))]
        assert len(measurement_items) == 0


# ---------------------------------------------------------------------------
# Config-driven font/pen in finish_measurement and update_measurement
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestConfigDrivenStyling:
    def _make_config(self):
        config = MagicMock()
        config.get_measurement_line_thickness.return_value = 3
        config.get_measurement_line_color.return_value = (255, 128, 0)
        config.get_measurement_font_size.return_value = 12
        config.get_measurement_font_color.return_value = (0, 128, 255)
        config.get_measurement_font_family.return_value = "Courier"
        config.get_measurement_font_variant.return_value = "Bold"
        return config

    def test_finish_with_config(self, qapp) -> None:
        config = self._make_config()
        tool = MeasurementTool(config_manager=config)
        tool.set_pixel_spacing((1.0, 1.0))
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _finish_distance(tool, scene, QPointF(0, 0), QPointF(5, 0))
        assert item is not None
        assert "mm" in item.text_item.toPlainText()

    def test_update_with_config(self, qapp) -> None:
        config = self._make_config()
        tool = MeasurementTool(config_manager=config)
        tool.set_pixel_spacing((1.0, 1.0))
        scene = _make_scene()
        tool.start_measurement(QPointF(0, 0))
        tool.update_measurement(QPointF(10, 10), scene)
        # Preview items should exist
        assert tool.current_line_item is not None
        assert tool.current_text_item is not None
        assert tool.current_text_item.toPlainText() != ""
        tool.cancel_measurement(scene)

    def test_angle_preview_with_config(self, qapp) -> None:
        config = self._make_config()
        tool = MeasurementTool(config_manager=config)
        scene = _make_scene()
        tool.handle_angle_click(QPointF(0, 0), scene)
        tool.handle_angle_click(QPointF(0, 50), scene)
        tool.update_angle_preview(QPointF(50, 50), scene)
        assert tool.angle_preview_text is not None
        assert tool.angle_preview_text.toPlainText() != ""

    def test_angle_commit_with_config(self, qapp) -> None:
        config = self._make_config()
        tool = MeasurementTool(config_manager=config)
        tool.set_current_slice("S", "SE", 0)
        scene = _make_scene()
        item = _place_angle(tool, scene, QPointF(0, 0), QPointF(0, 50), QPointF(50, 50))
        assert item is not None
        assert item.text_item.toPlainText() != ""


# ---------------------------------------------------------------------------
# Re-export backward compatibility
# ---------------------------------------------------------------------------

def test_re_exports_available() -> None:
    from tools.measurement_tool import (
        AngleMeasurementItem,
        DraggableAngleMeasurementText,
        DraggableMeasurementText,
        MeasurementHandle,
        MeasurementItem,
        MeasurementTool,
    )
    assert AngleMeasurementItem is not None
    assert DraggableAngleMeasurementText is not None
    assert DraggableMeasurementText is not None
    assert MeasurementHandle is not None
    assert MeasurementItem is not None
    assert MeasurementTool is not None
