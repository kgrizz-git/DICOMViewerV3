"""
Viewport-anchored overlay position helpers for OverlayManager.

Extracted from ``OverlayManager.update_overlay_positions`` to clear Sonar
``python:S3776`` (cognitive complexity) while preserving QWidget geometry sync
and QGraphicsItem corner repositioning on zoom/pan.

Inputs:
    - QGraphicsView / QGraphicsScene (or test doubles with the same API)
    - Corner overlay items and cached max widths

Outputs:
    - Updated widget geometry or scene item positions
    - Deferred scene/viewport invalidate for ItemIgnoresTransformations items

Requirements:
    - PySide6
    - ``graphics_view_uniform_zoom`` for scale under rotation/flip
"""

from __future__ import annotations

from typing import Any, NamedTuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGraphicsItem

from gui.view_transform_helpers import graphics_view_uniform_zoom
from utils.debug_flags import DEBUG_WIDGET_PAN

# Margin between overlay text and viewport edges, in viewport pixels.
OVERLAY_VIEWPORT_MARGIN_PX = 10


class CornerAnchor(NamedTuple):
    """One viewport-corner anchor in scene coordinates plus text alignment."""

    key: str
    x: float
    y: float
    alignment: Qt.AlignmentFlag


def sync_widget_overlay_geometry(widget: Any, view: Any) -> None:
    """
    Keep the viewport overlay widget at (0, 0) matching the viewport size.

    Label layout is owned by ``ViewportOverlayWidget.resizeEvent``; this only
    corrects widget geometry after pan/zoom when it has drifted.
    """
    viewport = view.viewport()
    if viewport is None:
        return

    current_geometry = widget.geometry()
    view_transform = view.transform()
    translation_x = view_transform.m31()
    translation_y = view_transform.m32()
    is_panning = abs(translation_x) > 0.01 or abs(translation_y) > 0.01

    if is_panning and DEBUG_WIDGET_PAN:
        _debug_log_widget_pan(widget, current_geometry, viewport, translation_x, translation_y)

    needs_geometry = (
        current_geometry.x() != 0
        or current_geometry.y() != 0
        or current_geometry.width() != viewport.width()
        or current_geometry.height() != viewport.height()
    )
    if not needs_geometry:
        return

    if is_panning and DEBUG_WIDGET_PAN:
        print(
            f"[DEBUG-WIDGET-PAN] Correcting widget geometry: {current_geometry} -> "
            f"(0, 0, {viewport.width()}, {viewport.height()})"
        )
    widget.setGeometry(0, 0, viewport.width(), viewport.height())


def _debug_log_widget_pan(
    widget: Any,
    current_geometry: Any,
    viewport: Any,
    translation_x: float,
    translation_y: float,
) -> None:
    """Emit pan diagnostics when DEBUG_WIDGET_PAN is enabled."""
    widget_pos = (current_geometry.x(), current_geometry.y())
    widget_size = (current_geometry.width(), current_geometry.height())
    viewport_size = (viewport.width(), viewport.height())
    print(
        f"[DEBUG-WIDGET-PAN] PAN detected: widget_pos={widget_pos}, "
        f"widget_size={widget_size}, viewport_size={viewport_size}, "
        f"transform_translation=({translation_x:.2f}, {translation_y:.2f})"
    )
    corner_labels = getattr(widget, "corner_labels", None) or {}
    for corner_key, label in corner_labels.items():
        if label.isVisible():
            print(f"[DEBUG-WIDGET-PAN] {corner_key} label position: {label.pos()}")


def resolve_view_for_scene(scene: Any, view: Any) -> Any | None:
    """
    Return a view associated with *scene*.

    Prefers *view* when ``view.scene()`` matches; otherwise uses the first
    view attached to the scene.
    """
    if view is not None and view.scene() == scene:
        return view
    views = scene.views()
    return views[0] if views else None


def build_viewport_corner_anchors(
    view: Any,
    margin_px: float = OVERLAY_VIEWPORT_MARGIN_PX,
) -> tuple[float, list[CornerAnchor]]:
    """
    Map viewport corners into scene space for overlay anchors.

    Returns:
        ``(viewport_to_scene_scale, corner_anchors)`` where scale converts
        viewport pixels to scene units under the current uniform zoom.
    """
    view_scale = graphics_view_uniform_zoom(view)
    viewport_to_scene_scale = 1.0 / view_scale
    margin_scene = margin_px * viewport_to_scene_scale

    viewport_width = view.viewport().width()
    viewport_height = view.viewport().height()
    top_left = view.mapToScene(0, 0)
    top_right = view.mapToScene(viewport_width, 0)
    bottom_left = view.mapToScene(0, viewport_height)
    bottom_right = view.mapToScene(viewport_width, viewport_height)

    # lower_right y intentionally uses bottom_left.y() (same as legacy layout).
    corners = [
        CornerAnchor(
            "upper_left",
            top_left.x() + margin_scene,
            top_left.y() + margin_scene,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        ),
        CornerAnchor(
            "upper_right",
            top_right.x(),
            top_right.y() + margin_scene,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        ),
        CornerAnchor(
            "lower_left",
            bottom_left.x() + margin_scene,
            bottom_left.y() - margin_scene,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        ),
        CornerAnchor(
            "lower_right",
            bottom_right.x(),
            bottom_left.y() - margin_scene,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        ),
    ]
    return viewport_to_scene_scale, corners


def filter_valid_overlay_items(items: list[Any], scene: Any) -> list[Any]:
    """Keep overlay items that still exist and belong to *scene*."""
    return [item for item in items if item is not None and item.scene() == scene]


def resolve_corner_max_width_viewport(
    cached_width: float,
    valid_items: list[Any],
) -> tuple[float, float | None]:
    """
    Resolve right-aligned corner max width in viewport pixels.

    Returns:
        ``(width, width_to_cache_or_None)``. When the cache is missing (0),
        recalculates from item bounding rects (+5px padding) and returns the
        value that should be stored in ``corner_max_width_map``.
    """
    if cached_width != 0:
        return cached_width, None

    max_text_width_viewport = 0.0
    for item in valid_items:
        if item is not None:
            max_text_width_viewport = max(max_text_width_viewport, item.boundingRect().width())
    max_text_width_viewport += 5
    to_cache = max_text_width_viewport if max_text_width_viewport > 0 else None
    return max_text_width_viewport, to_cache


def line_y_for_alignment(
    anchor_y: float,
    line_idx: int,
    line_count: int,
    line_spacing: float,
    align_bottom: bool,
) -> float:
    """Vertical scene Y for one line in a multi-line right-aligned corner."""
    if align_bottom:
        return anchor_y - (line_count - line_idx) * line_spacing
    return anchor_y + line_idx * line_spacing


def relocate_overlay_item(item: Any, scene: Any, x: float, y: float) -> None:
    """
    Move an ItemIgnoresTransformations overlay item and refresh dirty regions.

    Re-applies the ignore-transforms flag if it was lost, matching legacy
    defensive behavior during zoom/pan updates.
    """
    old_pos = item.pos()
    flags_before = item.flags()
    has_flag_before = bool(
        flags_before & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
    )

    item.prepareGeometryChange()
    old_rect = item.boundingRect().translated(old_pos)
    scene.invalidate(old_rect)

    item.setPos(x, y)

    if not has_flag_before:
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

    new_rect = item.boundingRect().translated(item.pos())
    scene.invalidate(new_rect)
    item.update()


def position_right_aligned_corner_items(
    *,
    valid_items: list[Any],
    scene: Any,
    anchor_x: float,
    anchor_y: float,
    alignment: Qt.AlignmentFlag,
    margin_scene: float,
    max_text_width_viewport: float,
    viewport_to_scene_scale: float,
) -> None:
    """Place one QGraphicsTextItem per line for a right-aligned corner."""
    if not valid_items:
        return

    max_text_width_scene = max_text_width_viewport * viewport_to_scene_scale
    right_edge_x = anchor_x - margin_scene
    left_edge_x = right_edge_x - max_text_width_scene

    line_height_viewport = valid_items[0].boundingRect().height()
    line_height_scene = line_height_viewport * viewport_to_scene_scale
    line_spacing = line_height_scene * 0.9
    align_bottom = bool(alignment & Qt.AlignmentFlag.AlignBottom)
    line_count = len(valid_items)

    for line_idx, item in enumerate(valid_items):
        if item is None:
            continue
        text_y = line_y_for_alignment(
            anchor_y, line_idx, line_count, line_spacing, align_bottom
        )
        relocate_overlay_item(item, scene, left_edge_x, text_y)


def position_left_aligned_corner_item(
    *,
    item: Any,
    scene: Any,
    x: float,
    y: float,
    alignment: Qt.AlignmentFlag,
    viewport_to_scene_scale: float,
) -> None:
    """Place a single (possibly multi-line) left-aligned corner item."""
    if item is None:
        return

    relocate_overlay_item(item, scene, x, y)

    if not (alignment & Qt.AlignmentFlag.AlignBottom):
        return

    text_height_scene = item.boundingRect().height() * viewport_to_scene_scale
    item.prepareGeometryChange()
    intermediate_rect = item.boundingRect().translated(item.pos())
    scene.invalidate(intermediate_rect)
    item.setPos(item.pos().x(), y - text_height_scene)


def schedule_scene_viewport_repaint(scene: Any, view: Any) -> None:
    """Defer full scene invalidate + viewport update until after the transform settles."""
    if view is None:
        return
    QTimer.singleShot(
        0,
        lambda: (
            scene.invalidate(),
            view.viewport().update(),
        ),
    )
