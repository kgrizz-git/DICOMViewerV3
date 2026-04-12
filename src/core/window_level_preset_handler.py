"""
Window/level preset application from the image context menu.

When the user picks a preset, stored center/width may be in raw or rescaled form.
This module aligns values with the current \"use rescaled values\" mode using the same
``DICOMProcessor`` conversions as ``SliceDisplayManager``, then updates toolbar controls,
status bar, and ``ViewStateManager`` flags.

Inputs:
    - ``app``: ``DICOMViewerApp`` (duck-typed: ``view_state_manager``, ``dicom_processor``,
      ``window_level_controls``, ``image_viewer``, ``main_window``)

Outputs:
    - Side effects only (no return value).

Requirements:
    - Qt widgets and DICOM stack already initialized on ``app``.
"""

from __future__ import annotations

from typing import Any


def apply_window_level_preset(app: Any, preset_index: int) -> None:
    """Apply the preset at ``preset_index`` if valid; no-op if presets or index are missing."""
    vsm = app.view_state_manager
    if not vsm or not vsm.window_level_presets:
        return
    if not (0 <= preset_index < len(vsm.window_level_presets)):
        return

    wc, ww, is_rescaled, preset_name = vsm.window_level_presets[preset_index]
    use_rescaled_values = vsm.use_rescaled_values
    rescale_slope = vsm.rescale_slope
    rescale_intercept = vsm.rescale_intercept

    if is_rescaled and not use_rescaled_values:
        if (
            rescale_slope is not None
            and rescale_intercept is not None
            and rescale_slope != 0.0
        ):
            wc, ww = app.dicom_processor.convert_window_level_rescaled_to_raw(
                wc, ww, rescale_slope, rescale_intercept
            )
    elif not is_rescaled and use_rescaled_values:
        if rescale_slope is not None and rescale_intercept is not None:
            wc, ww = app.dicom_processor.convert_window_level_raw_to_rescaled(
                wc, ww, rescale_slope, rescale_intercept
            )

    # block_signals=True: avoid handle_window_changed, which can re-run preset
    # matching against stale match_center/match_width and clobber current_preset_index.
    app.window_level_controls.set_window_level(wc, ww, block_signals=True)
    vsm.apply_window_level_from_context_menu_preset(wc, ww, preset_index)

    if app.image_viewer is not None:
        current_zoom = app.image_viewer.current_zoom
        preset_display_name = preset_name if preset_name else "Default"
        app.main_window.update_zoom_preset_status(current_zoom, preset_display_name)

    if hasattr(app, "_schedule_histogram_wl_only"):
        app._schedule_histogram_wl_only()
