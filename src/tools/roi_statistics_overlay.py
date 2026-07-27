"""
ROI statistics overlay formatting and scene placement helpers.

Extracted from ``ROIManager.create_statistics_overlay`` to clear Sonar
``python:S3776`` (cognitive complexity) while preserving text layout, font
scaling, and viewport-anchored placement for ``DraggableStatisticsOverlay``.

Inputs:
    - ROI item + statistics map
    - Optional font overrides and rescale unit suffix
    - QGraphicsScene (for item ensure/position/visibility)

Outputs:
    - Overlay text lines
    - Configured / positioned ``DraggableStatisticsOverlay`` item

Requirements:
    - PySide6, bundled fonts, ``graphics_view_uniform_zoom``
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QColor, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from gui.view_transform_helpers import graphics_view_uniform_zoom
from tools.roi_graphics_items import DraggableStatisticsOverlay
from utils.bundled_fonts import make_qfont

# Scalar ROI stats shown as one line each when selected in visible_statistics.
_SCALAR_STAT_LINES: tuple[tuple[str, str, str], ...] = (
    ("mean", "Mean", "mean"),
    ("std", "Std Dev", "std"),
    ("min", "Min", "min"),
    ("max", "Max", "max"),
)

# Per-channel summary rows: (visible key, stats key prefix, line label, value symbol).
_CHANNEL_STAT_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("mean", "mean_ch", "Ch mean", "μ"),
    ("std", "std_ch", "Ch std", "σ"),
    ("min", "min_ch", "Ch min", "min"),
    ("max", "max_ch", "Ch max", "max"),
)


def resolve_roi_overlay_font_style(
    config_manager: Any,
    font_size: int | None,
    font_color: tuple[int, int, int] | None,
) -> tuple[int, tuple[int, int, int], str, str]:
    """Resolve font size/color/family/variant from overrides or ROI config defaults."""
    if font_size is None:
        resolved_font_size = (
            config_manager.get_roi_font_size() if config_manager is not None else 6
        )
    else:
        resolved_font_size = font_size

    if font_color is None:
        resolved_color = (
            config_manager.get_roi_font_color() if config_manager else (255, 255, 0)
        )
    else:
        resolved_color = font_color

    font_family = (
        config_manager.get_roi_font_family() if config_manager else "IBM Plex Sans"
    )
    font_variant = config_manager.get_roi_font_variant() if config_manager else "Bold"
    return resolved_font_size, resolved_color, font_family, font_variant


def channel_labels_from_statistics(statistics: dict[str, Any], channel_count: int) -> tuple[str, ...]:
    """Return per-channel labels from stats, or ``Ch0..ChN-1`` fallbacks."""
    raw_lbl = statistics.get("channel_labels")
    if isinstance(raw_lbl, (list, tuple)) and len(raw_lbl) == channel_count:
        return tuple(str(x) for x in raw_lbl)
    return tuple(f"Ch{i}" for i in range(channel_count))


def append_channel_stat_lines(
    lines: list[str],
    *,
    visible_statistics: set[str],
    statistics: dict[str, Any],
    labels: tuple[str, ...],
    channel_count: int,
    unit_suffix: str,
) -> None:
    """Append multichannel mean/std/min/max summary lines when requested."""
    for visible_key, key_prefix, line_label, symbol in _CHANNEL_STAT_ROWS:
        if visible_key not in visible_statistics:
            continue
        bits: list[str] = []
        for c in range(channel_count):
            key = f"{key_prefix}{c}"
            if key not in statistics:
                continue
            lab = labels[c] if c < len(labels) else str(c)
            bits.append(f"{lab} {symbol}={statistics[key]:.2f}{unit_suffix}")
        if bits:
            lines.append(f"{line_label}: " + "  ".join(bits))


def format_area_overlay_line(statistics: dict[str, Any]) -> str:
    """Format the Area line using mm² / cm² when available, else pixels."""
    area_mm2 = statistics.get("area_mm2")
    if area_mm2 is not None:
        if area_mm2 >= 100:
            return f"Area: {area_mm2 / 100:.2f} cm²"
        return f"Area: {area_mm2:.2f} mm²"
    area_pixels = statistics.get("area_pixels", 0.0)
    return f"Area: {area_pixels:.1f} px"


def format_roi_statistics_overlay_lines(
    visible_statistics: set[str],
    statistics: dict[str, Any],
    rescale_type: str | None = None,
) -> list[str]:
    """Build statistics overlay text lines for the given visibility set."""
    lines: list[str] = []
    unit_suffix = f" {rescale_type}" if rescale_type else ""

    for visible_key, label, stats_key in _SCALAR_STAT_LINES:
        if visible_key in visible_statistics and stats_key in statistics:
            lines.append(f"{label}: {statistics[stats_key]:.2f}{unit_suffix}")

    mc = int(statistics.get("multichannel_count") or 0)
    if mc >= 2:
        labels = channel_labels_from_statistics(statistics, mc)
        append_channel_stat_lines(
            lines,
            visible_statistics=visible_statistics,
            statistics=statistics,
            labels=labels,
            channel_count=mc,
            unit_suffix=unit_suffix,
        )

    if "count" in visible_statistics and "count" in statistics:
        lines.append(f"Pixels: {statistics['count']}")
    if "area" in visible_statistics:
        lines.append(format_area_overlay_line(statistics))

    return lines


def ensure_draggable_statistics_overlay(
    roi: Any,
    scene: QGraphicsScene,
    offset_update_callback: Callable[[float, float], None],
) -> DraggableStatisticsOverlay:
    """Create or reuse the ROI's statistics overlay item for *scene*."""
    text_item = roi.statistics_overlay_item
    if text_item is None:
        return DraggableStatisticsOverlay(roi, offset_update_callback)

    old_scene = text_item.scene()
    if old_scene is not None and old_scene != scene:
        old_scene.removeItem(text_item)
    text_item.roi = roi
    text_item.offset_update_callback = offset_update_callback
    text_item.clear_deleted_flag()
    return text_item


def apply_statistics_overlay_font(
    text_item: DraggableStatisticsOverlay,
    *,
    font_size: int,
    font_color: tuple[int, int, int],
    font_family: str,
    font_variant: str,
) -> None:
    """Apply color/font, including sub-6pt scale transform used elsewhere for overlays."""
    text_item.setDefaultTextColor(QColor(*font_color))
    if font_size < 6:
        font = make_qfont(font_family, font_variant, 6)
        transform = QTransform()
        transform.scale(font_size / 6.0, font_size / 6.0)
        text_item.setTransform(transform)
    else:
        font = make_qfont(font_family, font_variant, font_size)
        # Clear any scale left from an earlier sub-6pt render on a reused item.
        text_item.setTransform(QTransform())
    text_item.setFont(font)


def configure_statistics_overlay_item_flags(text_item: DraggableStatisticsOverlay, roi: Any) -> None:
    """Set ignore-transform / movable flags and store ROI id user data."""
    text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
    text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
    text_item.setZValue(1001)
    text_item.setData(0, id(roi))


def statistics_overlay_scene_pos(roi: Any, scene: QGraphicsScene) -> tuple[float, float]:
    """Compute scene position for the overlay from ROI bounds + stored viewport offset."""
    bounds = roi.get_bounds()
    offset_x, offset_y = roi.statistics_overlay_offset
    view = scene.views()[0] if scene.views() else None
    if view is not None:
        viewport_to_scene_scale = 1.0 / graphics_view_uniform_zoom(view)
        return (
            bounds.right() + (offset_x * viewport_to_scene_scale),
            bounds.top() + (offset_y * viewport_to_scene_scale),
        )
    return bounds.right() + offset_x, bounds.top() + offset_y


def sync_statistics_overlay_scene_visibility(
    text_item: DraggableStatisticsOverlay, roi: Any, scene: QGraphicsScene
) -> None:
    """Add/show or hide the overlay according to ``roi.statistics_overlay_visible``."""
    if roi.statistics_overlay_visible:
        current_scene = text_item.scene()
        if current_scene is not None and current_scene != scene:
            current_scene.removeItem(text_item)
        if text_item.scene() != scene:
            scene.addItem(text_item)
        text_item.show()
    else:
        text_item.hide()
