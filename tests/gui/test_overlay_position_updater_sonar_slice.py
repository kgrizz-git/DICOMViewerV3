"""
Characterization tests for overlay position helpers (Sonar S3776 slice).

Covers pure helpers in ``overlay_position_updater`` plus
``OverlayManager.update_overlay_positions`` orchestration for widget and
graphics paths.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtWidgets import QGraphicsItem

from gui.overlay_manager import OverlayManager
from gui.overlay_position_updater import (
    OVERLAY_VIEWPORT_MARGIN_PX,
    build_viewport_corner_anchors,
    filter_valid_overlay_items,
    line_y_for_alignment,
    position_left_aligned_corner_item,
    position_right_aligned_corner_items,
    relocate_overlay_item,
    resolve_corner_max_width_viewport,
    resolve_view_for_scene,
    schedule_scene_viewport_repaint,
    sync_widget_overlay_geometry,
)


def test_line_y_for_alignment_top_and_bottom() -> None:
    assert line_y_for_alignment(100.0, 0, 3, 10.0, align_bottom=False) == 100.0
    assert line_y_for_alignment(100.0, 2, 3, 10.0, align_bottom=False) == 120.0
    # Bottom: y - (count - idx) * spacing
    assert line_y_for_alignment(100.0, 0, 3, 10.0, align_bottom=True) == 70.0
    assert line_y_for_alignment(100.0, 2, 3, 10.0, align_bottom=True) == 90.0


def test_resolve_corner_max_width_uses_cache() -> None:
    items = [MagicMock()]
    width, to_cache = resolve_corner_max_width_viewport(42.0, items)
    assert width == 42.0
    assert to_cache is None
    items[0].boundingRect.assert_not_called()


def test_resolve_corner_max_width_recalculates_when_cache_missing() -> None:
    a = MagicMock()
    a.boundingRect.return_value = SimpleNamespace(width=lambda: 20)
    b = MagicMock()
    b.boundingRect.return_value = SimpleNamespace(width=lambda: 35)

    width, to_cache = resolve_corner_max_width_viewport(0, [a, b])
    assert width == 40.0  # 35 + 5 padding
    assert to_cache == 40.0


def test_filter_valid_overlay_items() -> None:
    scene = object()
    other = object()
    good = MagicMock()
    good.scene.return_value = scene
    bad_scene = MagicMock()
    bad_scene.scene.return_value = other
    assert filter_valid_overlay_items([None, good, bad_scene], scene) == [good]


def test_resolve_view_for_scene_prefers_matching_view() -> None:
    scene = object()
    view = MagicMock()
    view.scene.return_value = scene
    assert resolve_view_for_scene(scene, view) is view


def test_resolve_view_for_scene_falls_back_to_scene_views() -> None:
    scene = MagicMock()
    other_view = MagicMock()
    scene.views.return_value = [other_view]
    wrong = MagicMock()
    wrong.scene.return_value = object()
    assert resolve_view_for_scene(scene, wrong) is other_view


def test_build_viewport_corner_anchors_keys_and_scale() -> None:
    view = MagicMock()
    view.viewport.return_value = MagicMock(width=MagicMock(return_value=200), height=MagicMock(return_value=100))
    # mapToScene(x,y) -> QPointF-like
    mapping = {
        (0, 0): QPointF(10.0, 20.0),
        (200, 0): QPointF(210.0, 20.0),
        (0, 100): QPointF(10.0, 120.0),
        (200, 100): QPointF(210.0, 120.0),
    }

    def map_to_scene(x, y):
        return mapping[(x, y)]

    view.mapToScene.side_effect = map_to_scene
    with patch(
        "gui.overlay_position_updater.graphics_view_uniform_zoom",
        return_value=2.0,
    ):
        scale, corners = build_viewport_corner_anchors(view, margin_px=10)

    assert scale == 0.5
    assert [c.key for c in corners] == [
        "upper_left",
        "upper_right",
        "lower_left",
        "lower_right",
    ]
    # margin_scene = 10 * 0.5 = 5
    assert corners[0].x == 15.0
    assert corners[0].y == 25.0
    assert corners[1].x == 210.0
    assert bool(corners[1].alignment & Qt.AlignmentFlag.AlignRight)
    # lower_right y uses bottom_left.y - margin (legacy)
    assert corners[3].y == 115.0
    assert corners[3].x == 210.0


def test_sync_widget_overlay_geometry_sets_when_drifted() -> None:
    widget = MagicMock()
    widget.geometry.return_value = QRect(5, 5, 100, 80)
    view = MagicMock()
    viewport = MagicMock()
    viewport.width.return_value = 200
    viewport.height.return_value = 150
    view.viewport.return_value = viewport
    transform = MagicMock()
    transform.m31.return_value = 0.0
    transform.m32.return_value = 0.0
    view.transform.return_value = transform

    sync_widget_overlay_geometry(widget, view)
    widget.setGeometry.assert_called_once_with(0, 0, 200, 150)


def test_sync_widget_overlay_geometry_noop_when_already_correct() -> None:
    widget = MagicMock()
    widget.geometry.return_value = QRect(0, 0, 200, 150)
    view = MagicMock()
    viewport = MagicMock()
    viewport.width.return_value = 200
    viewport.height.return_value = 150
    view.viewport.return_value = viewport
    transform = MagicMock()
    transform.m31.return_value = 0.0
    transform.m32.return_value = 0.0
    view.transform.return_value = transform

    sync_widget_overlay_geometry(widget, view)
    widget.setGeometry.assert_not_called()


def test_relocate_overlay_item_moves_and_reapplies_flag() -> None:
    item = MagicMock()
    item.pos.return_value = QPointF(1.0, 2.0)
    # Empty GraphicsItemFlag so ``flags & ItemIgnoresTransformations`` is valid and false.
    item.flags.return_value = QGraphicsItem.GraphicsItemFlag(0)
    item.boundingRect.return_value = QRectF(0, 0, 10, 5)
    scene = MagicMock()

    relocate_overlay_item(item, scene, 30.0, 40.0)

    item.prepareGeometryChange.assert_called()
    item.setPos.assert_called_with(30.0, 40.0)
    item.setFlag.assert_called_with(
        QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
    )
    item.update.assert_called()
    assert scene.invalidate.call_count >= 2


def test_position_right_aligned_uses_cached_width_and_line_spacing() -> None:
    item0 = MagicMock()
    item0.boundingRect.return_value = QRectF(0, 0, 50, 10)
    item0.pos.return_value = QPointF(0, 0)
    item0.flags.return_value = QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
    item1 = MagicMock()
    item1.boundingRect.return_value = QRectF(0, 0, 40, 10)
    item1.pos.return_value = QPointF(0, 0)
    item1.flags.return_value = QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
    scene = MagicMock()

    position_right_aligned_corner_items(
        valid_items=[item0, item1],
        scene=scene,
        anchor_x=100.0,
        anchor_y=20.0,
        alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        margin_scene=5.0,
        max_text_width_viewport=50.0,
        viewport_to_scene_scale=1.0,
    )
    # left_edge = (100 - 5) - 50 = 45; line spacing = 10 * 0.9 = 9
    item0.setPos.assert_called_with(45.0, 20.0)
    item1.setPos.assert_called_with(45.0, 29.0)


def test_position_left_aligned_bottom_adjusts_y() -> None:
    item = MagicMock()
    item.boundingRect.return_value = QRectF(0, 0, 30, 20)
    # relocate_overlay_item + bottom adjust both call pos(); keep returning the
    # post-move position after the first setPos.
    current = {"pos": QPointF(0.0, 0.0)}

    def _pos():
        return current["pos"]

    def _set_pos(x, y=None):
        if y is None:
            # QPointF overload — not used here
            current["pos"] = x
        else:
            current["pos"] = QPointF(x, y)

    item.pos.side_effect = _pos
    item.setPos.side_effect = _set_pos
    item.flags.return_value = QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
    scene = MagicMock()

    position_left_aligned_corner_item(
        item=item,
        scene=scene,
        x=10.0,
        y=90.0,
        alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        viewport_to_scene_scale=1.0,
    )
    # First setPos(10, 90), then setPos(x, y - height) => (10, 70)
    assert item.setPos.call_args_list[0] == call(10.0, 90.0)
    assert item.setPos.call_args_list[-1] == call(10.0, 70.0)
    assert current["pos"] == QPointF(10.0, 70.0)


@patch("gui.overlay_position_updater.QTimer.singleShot")
def test_schedule_scene_viewport_repaint(mock_shot) -> None:
    scene = MagicMock()
    view = MagicMock()
    schedule_scene_viewport_repaint(scene, view)
    mock_shot.assert_called_once()
    assert mock_shot.call_args[0][0] == 0


class TestUpdateOverlayPositionsOrchestration:
    def test_no_view_returns_early(self) -> None:
        mgr = OverlayManager(use_widget_overlays=False)
        scene = MagicMock()
        scene.views.return_value = []
        mgr.update_overlay_positions(scene)

    def test_widget_path_syncs_geometry(self) -> None:
        mgr = OverlayManager(use_widget_overlays=True)
        mgr.viewport_overlay_widget = MagicMock()
        scene = MagicMock()
        view = MagicMock()
        scene.views.return_value = [view]
        with patch(
            "gui.overlay_manager.sync_widget_overlay_geometry"
        ) as sync:
            mgr.update_overlay_positions(scene)
        sync.assert_called_once_with(mgr.viewport_overlay_widget, view)

    def test_graphics_path_recreates_on_stale_items(self) -> None:
        mgr = OverlayManager(use_widget_overlays=False)
        mgr.current_parser = MagicMock()
        mgr.overlay_items = [MagicMock()]
        stale = MagicMock()
        stale.scene.return_value = object()  # wrong scene
        mgr.corner_item_map["upper_left"] = [stale]
        mgr.current_total_slices = 9
        mgr.current_stack_position = 3

        scene = MagicMock()
        scene.sceneRect.return_value = QRectF(0, 0, 100, 100)
        view = MagicMock()
        view.scene.return_value = scene
        scene.views.return_value = [view]

        with (
            patch(
                "gui.overlay_manager.build_viewport_corner_anchors",
                return_value=(
                    1.0,
                    [
                        SimpleNamespace(
                            key="upper_left",
                            x=1.0,
                            y=2.0,
                            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                        )
                    ],
                ),
            ),
            patch.object(mgr, "create_overlay_items") as create,
            patch("gui.overlay_manager.schedule_scene_viewport_repaint") as sched,
        ):
            mgr.update_overlay_positions(scene)

        create.assert_called_once_with(
            scene,
            mgr.current_parser,
            total_slices=9,
            stack_position=3,
        )
        sched.assert_not_called()

    def test_graphics_path_positions_and_schedules_repaint(self) -> None:
        mgr = OverlayManager(use_widget_overlays=False)
        mgr.current_parser = MagicMock()
        mgr.overlay_items = [MagicMock()]
        item = MagicMock()
        item.scene.return_value = "scene-sentinel"
        mgr.corner_item_map["upper_left"] = [item]
        mgr.corner_max_width_map["upper_right"] = 50.0

        scene = MagicMock()
        scene.sceneRect.return_value = QRectF(0, 0, 100, 100)
        # Make filter_valid see matching scene
        item.scene.return_value = scene
        view = MagicMock()
        view.scene.return_value = scene
        scene.views.return_value = [view]

        corners = [
            SimpleNamespace(
                key="upper_left",
                x=5.0,
                y=6.0,
                alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            ),
            SimpleNamespace(
                key="upper_right",
                x=90.0,
                y=6.0,
                alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            ),
        ]
        # right corner empty map — skipped
        with (
            patch(
                "gui.overlay_manager.build_viewport_corner_anchors",
                return_value=(1.0, corners),
            ),
            patch(
                "gui.overlay_manager.position_left_aligned_corner_item"
            ) as left_pos,
            patch(
                "gui.overlay_manager.position_right_aligned_corner_items"
            ) as right_pos,
            patch("gui.overlay_manager.schedule_scene_viewport_repaint") as sched,
        ):
            mgr.update_overlay_positions(scene)

        left_pos.assert_called_once()
        right_pos.assert_not_called()
        sched.assert_called_once_with(scene, view)
        assert OVERLAY_VIEWPORT_MARGIN_PX == 10
