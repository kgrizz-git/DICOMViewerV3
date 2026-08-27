"""Small GUI-thread state helpers for responsive 3D volume first paint."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from core.volume_render_quality import (
    GpuFallbackOutcome,
    auto_detail_cap_index,
    should_auto_refine,
)

_EXPECTED_BLANK_GUIDANCE = (
    "Nothing is visible with this preset — try CT Soft Tissue or another preset."
)


def setup_first_paint_state(widget: Any) -> None:
    """Attach cancellable preview/refinement state and timers to a widget."""
    widget._cleaned_up = False
    widget._first_paint_pending = False
    widget._first_paint_complete = False
    widget._expected_blank_guidance = False
    widget._auto_refine_suppressed = False
    widget._auto_detail_capped = False
    widget._preview_timer = QTimer(widget)
    widget._preview_timer.setSingleShot(True)
    widget._preview_timer.timeout.connect(lambda: run_first_preview(widget))
    widget._refine_timer = QTimer(widget)
    widget._refine_timer.setSingleShot(True)
    widget._refine_timer.setInterval(80)
    widget._refine_timer.timeout.connect(lambda: refine_detail(widget))


def build_render_feedback_label(panel: QWidget) -> QLabel:
    """Create the visible, non-modal first-paint status label."""
    label = QLabel("", panel)
    label.setWordWrap(True)
    label.setStyleSheet(
        "background-color: #29455c; color: #e6f3ff; padding: 5px; "
        "border-radius: 3px; font-size: 11px;"
    )
    label.hide()
    return label


def schedule_first_preview(widget: Any) -> None:
    """Yield to Qt once so visible feedback can paint before VTK blocks."""
    widget._first_paint_pending = True
    widget._renderer.set_temporary_quality("Fast")
    set_render_feedback(widget, "Rendering 3D preview…")
    widget._preview_timer.start()


def run_first_preview(widget: Any) -> None:
    """Render Fast once, then schedule detail only after a responsive preview."""
    if (
        widget._cleaned_up
        or not widget._initialized
        or widget._vtk_render_window is None
        or not widget._first_paint_pending
    ):
        return
    set_render_feedback(widget, "Rendering 3D preview…")
    started = perf_counter()
    fallback_outcome = GpuFallbackOutcome.GPU_OK_VISIBLE
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        widget._vtk_render_window.Render()
        fallback_outcome = widget._renderer.check_gpu_fallback(
            widget._vtk_render_window, probe_quality="Fast"
        )
    finally:
        QApplication.restoreOverrideCursor()

    elapsed_ms = (perf_counter() - started) * 1000.0
    widget._first_paint_pending = False
    widget._first_paint_complete = True
    widget._expected_blank_guidance = (
        fallback_outcome is GpuFallbackOutcome.EXPECTED_BLANK
    )
    widget._update_render_status()
    if should_auto_refine(
        preview_elapsed_ms=elapsed_ms,
        gpu_fallback_used=fallback_outcome is GpuFallbackOutcome.FELL_BACK,
    ):
        if widget._expected_blank_guidance:
            set_render_feedback(widget, _EXPECTED_BLANK_GUIDANCE)
        else:
            set_render_feedback(widget, "3D preview ready — refining detail…")
        widget._refine_timer.start()
    else:
        widget._auto_refine_suppressed = True
        set_render_feedback(
            widget,
            _EXPECTED_BLANK_GUIDANCE
            if widget._expected_blank_guidance
            else (
                "3D preview shown at Fast detail. Higher Auto detail may be slow; "
                "choose a detail level manually to apply it."
            ),
        )


def check_interactive_gpu_fallback(widget: Any) -> None:
    """Re-probe an expected-blank frame after an interactive render.

    The renderer latches visible and CPU-fallback outcomes, so this stays a
    cheap no-op except after an expected-blank preview whose transfer function
    may have changed.
    """
    if not widget._first_paint_complete or widget._vtk_render_window is None:
        return
    outcome = widget._renderer.check_gpu_fallback(widget._vtk_render_window)
    if outcome is not GpuFallbackOutcome.EXPECTED_BLANK:
        widget._expected_blank_guidance = False
        set_render_feedback(widget, "")
    if outcome is GpuFallbackOutcome.FELL_BACK:
        widget._update_render_status()


def render_interactive_frame(widget: Any) -> None:
    """Render an interactive frame and perform its conditional fallback probe."""
    if widget._initialized and widget._surface is not None:
        widget._surface.render_frame()
        check_interactive_gpu_fallback(widget)


def refine_detail(widget: Any) -> None:
    """Apply selected target detail after the responsive-preview gate."""
    if (
        widget._cleaned_up
        or not widget._initialized
        or widget._vtk_render_window is None
        or widget._auto_refine_suppressed
    ):
        return
    set_render_feedback(widget, "Refining 3D detail…")
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        widget._renderer.restore_target_quality()
        widget._vtk_render_window.Render()
    finally:
        QApplication.restoreOverrideCursor()
    set_render_feedback(
        widget,
        _EXPECTED_BLANK_GUIDANCE if widget._expected_blank_guidance else "",
    )
    widget._update_render_status()


def volume_input_bytes(renderer: Any) -> int | None:
    """Return attached float32 VTK input size without retaining image data."""
    try:
        volumes = renderer.get_renderer().GetVolumes()
        volumes.InitTraversal()
        volume = volumes.GetNextVolume()
        mapper = volume.GetMapper() if volume is not None else None
        image = mapper.GetInput() if mapper is not None else None
        dims = image.GetDimensions() if image is not None else None
        if dims is None or len(dims) != 3:
            return None
        return int(dims[0]) * int(dims[1]) * int(dims[2]) * 4
    except Exception:
        return None


def set_render_feedback(widget: Any, text: str) -> None:
    """Show visible non-modal status without relying on Advanced controls."""
    label = getattr(widget, "_render_feedback_label", None)
    if label is not None:
        label.setText(text)
        label.setVisible(bool(text))


def cancel_pending_refine(widget: Any) -> None:
    """Stop the owned refinement timer before changes or VTK teardown."""
    if widget._refine_timer.isActive():
        widget._refine_timer.stop()


def auto_detail_target(renderer: Any, *, steep: bool, mode_count: int) -> tuple[int, bool]:
    """Select capped Auto Detail from a preset steepness and VTK input size."""
    target = 2 if steep else 1
    capped_target = min(
        target, auto_detail_cap_index(volume_input_bytes(renderer), mode_count=mode_count)
    )
    return capped_target, capped_target < target


def apply_interaction_detail(widget: Any, *, low: bool) -> None:
    """Keep slow automatic previews at Fast through interaction events."""
    if widget._auto_refine_suppressed or (low and widget._first_paint_pending):
        widget._renderer.set_temporary_quality("Fast")
    else:
        widget._renderer.set_interactive_quality(low)


def stop_first_paint_timers(widget: Any) -> None:
    """Prevent queued preview/refinement or debounce render after teardown."""
    widget._preview_timer.stop()
    cancel_pending_refine(widget)
    widget._render_timer.stop()
