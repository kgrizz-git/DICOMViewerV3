"""Focused tests for OverlayManager controls and graphics/widget corner overlays."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QWidget

from gui.overlay_manager import OverlayManager, ViewportOverlayWidget


@pytest.mark.qt
def test_viewport_overlay_setters_and_clear(qapp) -> None:
    parent = QWidget()
    widget = ViewportOverlayWidget(parent, font_size=8)
    widget.set_corner_text("upper_left", "UL", Qt.AlignmentFlag.AlignLeft)
    widget.set_corner_text("upper_right", "UR", Qt.AlignmentFlag.AlignRight)
    widget.set_mpr_banner("MPR Axial")
    widget.set_font_size(10)
    widget.set_font_family("IBM Plex Sans")
    widget.set_font_variant("Regular")
    widget.set_font_color((0, 255, 0))
    widget.update_positions(200, 150)

    assert widget.mpr_banner_label is not None
    assert "MPR Axial" in widget.mpr_banner_label.text()
    widget.clear_all()
    assert widget.mpr_banner_label.text() == ""
    assert not widget.mpr_banner_label.isVisible()


@pytest.mark.qt
def test_overlay_manager_mode_and_visibility_cycle(qapp) -> None:
    mgr = OverlayManager(font_size=7, font_color=(255, 0, 0), config_manager=None)
    assert mgr.mode == "minimal"
    assert mgr.visibility_state == 0
    assert mgr.should_show_text_overlays() is True

    mgr.set_mode("detailed")
    assert mgr.mode == "detailed"
    mgr.set_mode("hidden")
    assert mgr.mode == "hidden"
    assert mgr.should_show_text_overlays() is False

    state1 = mgr.toggle_overlay_visibility()
    assert state1 == 1
    assert mgr.visibility_state == 1
    mgr.set_visibility_state(2)
    assert mgr.visibility_state == 2
    assert mgr.should_show_text_overlays() is False
    mgr.set_mode("minimal")
    mgr.set_visibility_state(0)
    assert mgr.should_show_text_overlays() is True


@pytest.mark.qt
def test_overlay_manager_font_privacy_and_custom_fields(qapp) -> None:
    mgr = OverlayManager()
    mgr.set_custom_fields(["PatientID", "StudyDate"])
    assert mgr.custom_fields == ["PatientID", "StudyDate"]

    mgr.set_font_size(12)
    mgr.set_font_color(10, 20, 30)
    mgr.set_font_family("Courier New")
    mgr.set_font_variant("Bold")
    assert mgr.font_size == 12
    assert mgr.font_color == (10, 20, 30)
    assert mgr.font_family == "Courier New"
    assert mgr.font_variant == "Bold"

    mgr.set_privacy_mode(True)
    assert mgr.privacy_mode is True
    mgr.set_mpr_banner("Sagittal")
    # Banner is applied when a viewport widget exists; ensure no crash without one.
    assert mgr.viewport_overlay_widget is None

    tags = mgr._corner_tags_for_current_mode("CT")
    assert isinstance(tags, dict)
    assert set(tags.keys()) >= {"upper_left", "upper_right", "lower_left", "lower_right"}


@pytest.mark.qt
def test_overlay_manager_clear_items_noop_without_scene(qapp) -> None:
    mgr = OverlayManager()
    scene = MagicMock()
    scene.items.return_value = []
    mgr.clear_overlay_items(scene)
    assert mgr.overlay_items == []
    for corner_items in mgr.corner_item_map.values():
        assert corner_items == []


@pytest.mark.qt
def test_create_overlay_items_delegates_to_widget_before_graphics_cleanup(qapp) -> None:
    manager = OverlayManager(use_widget_overlays=True)
    scene = MagicMock()
    view = MagicMock()
    parser = MagicMock()
    scene.views.return_value = [view]
    multiframe_context = {"frame_index": 3}

    with (
        patch.object(manager, "_create_widget_overlays", return_value=[]) as create_widget,
        patch.object(manager, "clear_overlay_items") as clear_graphics,
    ):
        result = manager.create_overlay_items(
            scene,
            parser,
            total_slices=12,
            projection_enabled=True,
            projection_start_slice=2,
            projection_end_slice=7,
            projection_total_thickness=10.5,
            projection_type="mip",
            multiframe_context=multiframe_context,
            stack_position=4,
        )

    assert result == []
    create_widget.assert_called_once_with(
        view, parser, 12, True, 2, 7, 10.5, "mip", multiframe_context, 4
    )
    clear_graphics.assert_not_called()
    assert manager.current_parser is parser
    assert manager.current_scene is scene
    assert manager.current_total_slices == 12
    assert manager.current_stack_position == 4
    assert manager.current_projection_enabled is True
    assert manager.current_multiframe_context is multiframe_context


@pytest.mark.qt
def test_create_overlay_items_clears_graphics_before_hidden_return(qapp) -> None:
    manager = OverlayManager(use_widget_overlays=False)
    manager.set_mode("hidden")
    scene = MagicMock()
    parser = MagicMock()
    scene.views.return_value = []
    manager.corner_item_map["upper_left"].append(MagicMock())

    with patch.object(manager, "clear_overlay_items") as clear_graphics:
        result = manager.create_overlay_items(scene, parser, stack_position=2)

    assert result == []
    clear_graphics.assert_called_once_with(scene)
    assert all(not items for items in manager.corner_item_map.values())
    assert manager.current_parser is parser
    assert manager.current_stack_position == 2


@pytest.mark.qt
def test_graphics_overlay_fallback_anchors_without_view(qapp) -> None:
    manager = OverlayManager(use_widget_overlays=False)
    scene = MagicMock()
    scene.views.return_value = []
    scene.sceneRect.return_value = QRectF()
    scene.items.return_value = []
    parser = MagicMock()

    with (
        patch("gui.overlay_manager.get_modality", return_value="CT"),
        patch.object(manager, "_render_graphics_corner") as render_corner,
    ):
        manager.create_overlay_items(scene, parser)

    anchors = [
        (args.args[2], args.args[3], args.args[4])
        for args in render_corner.call_args_list
    ]
    assert anchors == [
        ("upper_left", 10, 10),
        ("upper_right", 790, 10),
        ("lower_left", 10, 590),
        ("lower_right", 790, 590),
    ]


@pytest.mark.qt
def test_graphics_overlay_uses_largest_item_when_scene_rect_is_empty(qapp) -> None:
    scene = MagicMock()
    small_item = MagicMock()
    large_item = MagicMock()
    scene.sceneRect.return_value = QRectF()
    scene.items.return_value = [small_item, large_item]
    small_item.boundingRect.return_value = QRectF(0, 0, 100, 100)
    large_item.boundingRect.return_value = QRectF(0, 0, 220, 120)

    assert OverlayManager._resolve_scene_dimensions(scene) == (220.0, 120.0)


@pytest.mark.qt
def test_graphics_overlay_viewport_anchors_preserve_legacy_lower_right(qapp) -> None:
    manager = OverlayManager(use_widget_overlays=False)
    scene = MagicMock()
    view = MagicMock()
    viewport = MagicMock()
    parser = MagicMock()
    viewport.width.return_value = 200
    viewport.height.return_value = 100
    view.viewport.return_value = viewport
    scene.views.return_value = [view]
    scene.sceneRect.return_value = QRectF(0, 0, 400, 300)
    coordinate_map = {
        (0, 0): QPointF(10, 20),
        (200, 0): QPointF(210, 20),
        (0, 100): QPointF(10, 120),
        (200, 100): QPointF(210, 120),
    }
    view.mapToScene.side_effect = lambda x, y: coordinate_map[(x, y)]

    with (
        patch("gui.overlay_manager.get_modality", return_value="CT"),
        patch("gui.overlay_manager.graphics_view_uniform_zoom", return_value=2.0),
        patch.object(manager, "_render_graphics_corner") as render_corner,
    ):
        manager.create_overlay_items(scene, parser)

    anchors = [
        (args.args[2], args.args[3], args.args[4])
        for args in render_corner.call_args_list
    ]
    assert anchors == [
        ("upper_left", 15.0, 25.0),
        ("upper_right", 210.0, 25.0),
        ("lower_left", 15.0, 115.0),
        ("lower_right", 210.0, 115.0),
    ]


@pytest.mark.qt
def test_right_aligned_graphics_lines_cache_width_and_stack_from_bottom(qapp) -> None:
    manager = OverlayManager(use_widget_overlays=False)
    scene = MagicMock()
    temporary_one = MagicMock()
    temporary_two = MagicMock()
    temporary_one.boundingRect.return_value = SimpleNamespace(width=lambda: 20)
    temporary_two.boundingRect.return_value = SimpleNamespace(width=lambda: 40)
    first_line = MagicMock()
    second_line = MagicMock()
    first_line.boundingRect.return_value = SimpleNamespace(height=lambda: 10)

    with patch.object(
        manager,
        "_create_text_item",
        side_effect=[temporary_one, temporary_two, first_line, second_line],
    ) as create_text_item:
        manager._render_right_aligned_corner(
            scene,
            "lower_right",
            "First\n\nSecond",
            x=100,
            y=200,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            margin_scene=5,
            viewport_to_scene_scale=0.5,
        )

    assert manager.corner_max_width_map["lower_right"] == 45
    assert create_text_item.call_args_list == [
        call("First", 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
        call("Second", 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
        call(
            "First",
            0,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            text_width=45,
        ),
        call(
            "Second",
            0,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            text_width=45,
        ),
    ]
    assert first_line.setPos.call_args == call(72.5, 191.0)
    assert second_line.setPos.call_args == call(72.5, 195.5)
    assert manager.corner_item_map["lower_right"] == [first_line, second_line]
    assert scene.addItem.call_args_list == [call(first_line), call(second_line)]


@pytest.mark.qt
def test_left_aligned_bottom_graphics_text_keeps_multiline_bottom_anchor(qapp) -> None:
    manager = OverlayManager(use_widget_overlays=False)
    scene = MagicMock()
    text_item = MagicMock()
    text_item.boundingRect.return_value = SimpleNamespace(height=lambda: 20)
    text_item.pos.return_value = QPointF(10, 100)

    with patch.object(manager, "_create_text_item", return_value=text_item):
        manager._render_left_aligned_corner(
            scene,
            "lower_left",
            "Line one\nLine two",
            x=10,
            y=100,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            viewport_to_scene_scale=0.5,
        )

    assert text_item.setPos.call_args_list == [call(10, 100), call(10.0, 90.0)]
    assert manager.corner_item_map["lower_left"] == [text_item]
    scene.addItem.assert_called_once_with(text_item)


@pytest.mark.qt
def test_graphics_overlay_forwards_text_context_unchanged(qapp) -> None:
    config_manager = MagicMock()
    config_manager.get_overlay_tags.return_value = {
        "upper_left": ["InstanceNumber"],
        "upper_right": [],
        "lower_left": [],
        "lower_right": [],
    }
    manager = OverlayManager(use_widget_overlays=False, config_manager=config_manager)
    manager.set_privacy_mode(True)
    scene = MagicMock()
    parser = MagicMock()
    multiframe_context = {"frame_index": 2, "frame_count": 5}
    scene.views.return_value = []
    scene.sceneRect.return_value = QRectF(0, 0, 800, 600)

    with (
        patch("gui.overlay_manager.get_modality", return_value="CT"),
        patch("gui.overlay_manager.get_corner_text", return_value="Slice 2/5") as corner_text,
        patch.object(manager, "_render_left_aligned_corner"),
    ):
        manager.create_overlay_items(
            scene,
            parser,
            total_slices=5,
            projection_enabled=True,
            projection_start_slice=1,
            projection_end_slice=3,
            projection_total_thickness=4.5,
            projection_type="aip",
            multiframe_context=multiframe_context,
            stack_position=2,
        )

    corner_text.assert_called_once_with(
        parser,
        ["InstanceNumber"],
        True,
        5,
        True,
        1,
        3,
        4.5,
        "aip",
        multiframe_context,
        2,
    )
