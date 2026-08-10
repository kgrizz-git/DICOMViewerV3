"""Detail-control behavior shared by the 3D volume viewer UI."""

from __future__ import annotations

from typing import Any

from core.volume_renderer import QUALITY_MODES, TransferFunctionPreset, is_steep_preset
from gui.volume.first_paint import auto_detail_target, cancel_pending_refine


def caption_text(index: int, *, auto: bool, capped: bool) -> str:
    """Return the honest Detail caption for selected Auto/manual state."""
    name = QUALITY_MODES[index][0] if 0 <= index < len(QUALITY_MODES) else ""
    if auto and capped:
        return f"Detail: {name} (auto, capped for volume)"
    return f"Detail: {name} (auto)" if auto else f"Detail: {name}"


def apply_detail_index(widget: Any, index: int, *, apply: bool = True) -> None:
    """Push a detail target into renderer state and refresh widget labels."""
    index = max(0, min(len(QUALITY_MODES) - 1, index))
    widget._renderer.set_quality_mode(QUALITY_MODES[index][0], apply=apply)
    widget._detail_caption.setText(
        caption_text(
            index,
            auto=widget._detail_auto_cb.isChecked(),
            capped=widget._auto_detail_capped,
        )
    )
    widget._update_overlay_text()


def apply_auto_detail(widget: Any, preset: TransferFunctionPreset | None = None) -> None:
    """Apply steepness-aware, volume-capped Auto Detail to the widget."""
    if not widget._detail_auto_cb.isChecked():
        return
    cancel_pending_refine(widget)
    if preset is None:
        preset = widget._current_preset_object()
    target, widget._auto_detail_capped = auto_detail_target(
        widget._renderer,
        steep=preset is not None and is_steep_preset(preset),
        mode_count=len(QUALITY_MODES),
    )
    widget._detail_slider.blockSignals(True)
    widget._detail_slider.setValue(target)
    widget._detail_slider.blockSignals(False)
    apply_detail_index(widget, target)
