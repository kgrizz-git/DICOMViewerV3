"""
Window/level resolution for series transitions in slice display.

Determines the correct window center/width and rescale mode when the viewer
transitions between studies or series.  Extracted from
``SliceDisplayManager._resolve_window_level_for_series_transition`` and
``SliceDisplayManager._compute_series_transition_state``.

Inputs: SliceDisplayManager instance (``mgr``), DICOM Dataset, study/series
        context, rescale parameters.
Outputs: (window_center, window_width, use_rescaled_values) or transition
         state tuples.
Requirements: core.dicom_processor, core.wl_preset_catalog,
              core.slice_display_lut, utils.dicom_utils, utils.debug_flags.
"""

from typing import Any

import numpy as np
from pydicom.dataset import Dataset

from core.slice_display_lut import apply_window_level_rescale_conversion
from core.wl_preset_catalog import build_preset_list, presets_to_legacy
from utils.debug_flags import DEBUG_MEASUREMENT_SERIES, DEBUG_WL
from utils.dicom_utils import get_composite_series_key

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _set_rescale_toggle_state(mgr: Any, checked: bool) -> None:
    """Update injected rescale toggle targets without importing GUI modules."""
    main_window = getattr(mgr.view_state_manager, "main_window", None)
    if main_window is not None and hasattr(main_window, "set_rescale_toggle_state"):
        main_window.set_rescale_toggle_state(checked)
    image_viewer = getattr(mgr, "image_viewer", None)
    if image_viewer is not None and hasattr(image_viewer, "set_rescale_toggle_state"):
        image_viewer.set_rescale_toggle_state(checked)


def _init_new_series_state(
    mgr: Any,
    dataset: Dataset,
    rescale_slope: float | None,
    rescale_intercept: float | None,
    series_identifier: str,
) -> None:
    """Save previous user W/L, set rescale toggle, reset current W/L."""
    mgr.view_state_manager.save_user_window_level()
    use_rescaled = rescale_slope is not None and rescale_intercept is not None
    mgr.view_state_manager.use_rescaled_values = use_rescaled
    _set_rescale_toggle_state(mgr, use_rescaled)
    mgr.view_state_manager.set_current_series_identifier(series_identifier)
    mgr.view_state_manager.current_window_center = None
    mgr.view_state_manager.current_window_width = None
    mgr.view_state_manager.window_level_user_modified = False


def _build_presets_and_extract_wl(
    mgr: Any,
    dataset: Dataset,
    rescale_slope: float | None,
    rescale_intercept: float | None,
    debug_label: str,
) -> tuple[float | None, float | None, bool]:
    """Build merged preset list, extract W/L from first preset or dataset.

    *debug_label* controls whether debug prints say ``"embedded"`` or
    ``"fallback"`` (or any other caller-supplied tag).

    Returns ``(wc, ww, is_rescaled)``.
    """
    _merged = build_preset_list(
        dataset,
        mgr.dicom_processor,
        mgr.config_manager,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
    )
    mgr.view_state_manager.window_level_presets = presets_to_legacy(_merged)
    mgr.view_state_manager._wl_preset_objects = _merged  # type: ignore[attr-defined]
    presets = mgr.dicom_processor.get_window_level_presets_from_dataset(
        dataset,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
    )
    mgr.view_state_manager.current_preset_index = 0
    mgr.view_state_manager.window_level_user_modified = False

    if presets:
        wc, ww, is_rescaled, _ = presets[0]
        if DEBUG_WL:
            print(f"[DEBUG-WL] {debug_label} from first preset: wc={wc} ww={ww} is_rescaled={is_rescaled}")
    else:
        wc, ww, is_rescaled = mgr.dicom_processor.get_window_level_from_dataset(
            dataset,
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept,
        )
        if DEBUG_WL:
            print(f"[DEBUG-WL] {debug_label} from get_window_level_from_dataset: wc={wc} ww={ww} is_rescaled={is_rescaled}")

    return wc, ww, is_rescaled


def _compute_pixel_range_wl(
    mgr: Any,
    dataset: Dataset,
    series_datasets: list[Dataset],
    use_rescaled_values: bool,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Compute series pixel range, then W/L from pixel range if no embedded W/L.

    Tries series-level pixel range first (with median), then falls back to
    single-slice pixel range.

    Returns ``(stored_window_center, stored_window_width,
    series_pixel_min, series_pixel_max)``.
    """
    series_pixel_min: float | None = None
    series_pixel_max: float | None = None
    stored_window_center: float | None = None
    stored_window_width: float | None = None

    try:
        series_pixel_min, series_pixel_max = mgr.dicom_processor.get_series_pixel_value_range(
            series_datasets, apply_rescale=use_rescaled_values
        )
        mgr.view_state_manager.set_series_pixel_range(series_pixel_min, series_pixel_max)
    except Exception as e:
        error_type = type(e).__name__
        print(f"Error calculating series pixel range ({error_type}): {e}")
        series_pixel_min = None
        series_pixel_max = None
        mgr.view_state_manager.clear_series_pixel_range()

    return stored_window_center, stored_window_width, series_pixel_min, series_pixel_max


def _compute_wl_from_series_pixel_range(
    mgr: Any,
    series_datasets: list[Dataset],
    series_pixel_min: float,
    series_pixel_max: float,
    use_rescaled_values: bool,
) -> tuple[float, float]:
    """Compute W/L from series pixel range using median heuristic.

    Returns ``(stored_window_center, stored_window_width)``.
    """
    midpoint = (series_pixel_min + series_pixel_max) / 2.0
    if series_datasets:
        median = mgr.dicom_processor.get_series_pixel_median(
            series_datasets, apply_rescale=use_rescaled_values
        )
        if median is None:
            stored_window_center = midpoint
        else:
            stored_window_center = max(median, midpoint)
    else:
        stored_window_center = midpoint

    stored_window_width = series_pixel_max - series_pixel_min
    if stored_window_width <= 0:
        stored_window_width = 1.0
    if DEBUG_WL:
        print(
            f"[DEBUG-WL] from series pixel range: min={series_pixel_min} max={series_pixel_max} "
            f"stored_wc={stored_window_center} stored_ww={stored_window_width}"
        )
    return stored_window_center, stored_window_width


def _compute_wl_from_single_slice(
    mgr: Any,
    dataset: Dataset,
    use_rescaled_values: bool,
) -> tuple[float | None, float | None]:
    """Compute W/L from a single dataset's pixel data (fallback).

    Returns ``(stored_window_center, stored_window_width)`` or
    ``(None, None)`` on failure.
    """
    stored_window_center: float | None = None
    stored_window_width: float | None = None
    try:
        pixel_min, pixel_max = mgr.dicom_processor.get_pixel_value_range(
            dataset, apply_rescale=use_rescaled_values
        )
        if pixel_min is not None and pixel_max is not None:
            pixel_array = mgr.dicom_processor.get_pixel_array(dataset)
            if pixel_array is not None:
                if use_rescaled_values:
                    rs, ri, _ = mgr.dicom_processor.get_rescale_parameters(dataset)
                    if rs is not None and ri is not None:
                        pixel_array = pixel_array.astype(np.float32) * float(rs) + float(ri)
                midpoint = (pixel_min + pixel_max) / 2.0
                non_zero_values = pixel_array[pixel_array != 0]
                if len(non_zero_values) > 0:
                    median = float(np.median(non_zero_values))
                    stored_window_center = max(median, midpoint)
                else:
                    stored_window_center = midpoint
            else:
                stored_window_center = (pixel_min + pixel_max) / 2.0
            stored_window_width = pixel_max - pixel_min
            if stored_window_width is not None and stored_window_width <= 0:
                stored_window_width = 1.0
    except Exception as e:
        error_type = type(e).__name__
        print(f"Error calculating single slice pixel range ({error_type}): {e}")
    return stored_window_center, stored_window_width


def _apply_rescale_and_store_defaults(
    mgr: Any,
    wc: float | None,
    ww: float | None,
    is_rescaled: bool,
    use_rescaled_values: bool,
    rescale_slope: float | None,
    rescale_intercept: float | None,
    debug_label: str,
) -> tuple[float | None, float | None]:
    """Apply rescale conversion to W/L and emit debug trace.

    Returns the converted ``(wc, ww)`` pair.  If *wc* or *ww* is ``None``,
    returns ``(None, None)`` unchanged.
    """
    if wc is None or ww is None:
        return None, None
    orig_wc, orig_ww = wc, ww
    wc, ww = apply_window_level_rescale_conversion(
        wc,
        ww,
        is_rescaled=is_rescaled,
        use_rescaled_values=use_rescaled_values,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
        dicom_processor=mgr.dicom_processor,
    )
    if DEBUG_WL and (wc != orig_wc or ww != orig_ww):
        print(
            f"[DEBUG-WL] {debug_label} WL rescale conversion: ({orig_wc}, {orig_ww}) -> ({wc}, {ww})"
        )
    return wc, ww


def _store_wl_and_defaults(
    mgr: Any,
    window_center: float,
    window_width: float,
    use_rescaled_values: bool,
    series_identifier: str,
) -> None:
    """Store W/L on view_state_manager, update zoom/preset status, write series_defaults."""
    mgr.view_state_manager.current_window_center = window_center
    mgr.view_state_manager.current_window_width = window_width

    current_zoom = mgr.image_viewer.current_zoom
    unit = mgr.view_state_manager.window_level_controls.unit
    mgr.view_state_manager.main_window.update_zoom_preset_status(
        current_zoom, window_center, window_width, unit=unit
    )

    if series_identifier not in mgr.view_state_manager.series_defaults:
        mgr.view_state_manager.series_defaults[series_identifier] = {}
    mgr.view_state_manager.series_defaults[series_identifier].update({
        'window_center': window_center,
        'window_width': window_width,
        'use_rescaled_values': use_rescaled_values,
        'image_inverted': mgr.image_viewer.image_inverted,
        'window_level_defaults_set': True,
    })


def _restore_user_wl_cache(
    mgr: Any,
    series_identifier: str,
) -> tuple[float | None, float | None]:
    """Check for cached user W/L and restore if found.

    Returns ``(window_center, window_width)`` when a cache hit occurs,
    or ``(None, None)`` otherwise.
    """
    cached_wl = mgr.view_state_manager.get_user_window_level(series_identifier)
    if cached_wl is not None:
        wc = cached_wl["window_center"]
        ww = cached_wl["window_width"]
        mgr.view_state_manager.current_window_center = wc
        mgr.view_state_manager.current_window_width = ww
        mgr.view_state_manager.window_level_user_modified = True
        return wc, ww
    return None, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_series_transition_state(
    mgr: Any,
    dataset: Dataset,
    current_series_uid: str,
    current_slice_index: int,
) -> tuple[str, bool, bool, str]:
    """Compute same-series and new-series transition flags for the incoming dataset."""
    new_series_uid = get_composite_series_key(dataset)
    is_same_series = new_series_uid == current_series_uid and current_series_uid != ""
    previous_series_identifier = mgr.view_state_manager.current_series_identifier
    is_new_study_series = mgr.view_state_manager.is_new_study_or_series(dataset)
    series_identifier = mgr.view_state_manager.get_series_identifier(dataset)
    if DEBUG_MEASUREMENT_SERIES:
        print(
            "[DEBUG-MEAS-SERIES] display_slice enter: "
            f"{mgr._measurement_debug_prefix(dataset, current_slice_index)}, "
            f"arg_current_series_uid={current_series_uid}, computed_series_uid={new_series_uid}, "
            f"previous_series_identifier={previous_series_identifier}, "
            f"incoming_series_identifier={series_identifier}, is_same_series={is_same_series}, "
            f"is_new_study_series={is_new_study_series}, "
            f"measurement_summary={mgr.measurement_tool.get_debug_summary(mgr.image_viewer.scene)}"
        )
    return new_series_uid, is_same_series, is_new_study_series, series_identifier


def resolve_window_level_for_series_transition(
    mgr: Any,
    dataset: Dataset,
    current_studies: dict[str, dict[str, list[Dataset]]],
    current_series_uid: str,
    new_series_uid: str,
    is_same_series: bool,
    is_new_study_series: bool,
    series_identifier: str,
    rescale_slope: float | None,
    rescale_intercept: float | None,
) -> tuple[float | None, float | None, bool]:
    """Resolve window/level and rescale mode across same-series vs new-series transitions."""

    # -- 1. If new study/series: initialise rescale state, reset W/L ---------
    if is_new_study_series:
        _init_new_series_state(mgr, dataset, rescale_slope, rescale_intercept, series_identifier)

    # -- 2. Determine use_rescaled_values ------------------------------------
    window_center = mgr.view_state_manager.current_window_center
    window_width = mgr.view_state_manager.current_window_width
    if is_new_study_series:
        use_rescaled_values = rescale_slope is not None and rescale_intercept is not None
    else:
        use_rescaled_values = mgr.view_state_manager.use_rescaled_values

    # -- 3. Debug log entry --------------------------------------------------
    if DEBUG_WL:
        study_uid = getattr(dataset, 'StudyInstanceUID', '')[:24] if getattr(dataset, 'StudyInstanceUID', '') else ''
        modality = getattr(dataset, 'Modality', '?')
        print(
            f"[DEBUG-WL] display_slice ENTER: study={study_uid}... series={new_series_uid[:24] if new_series_uid else ''}... "
            f"modality={modality} is_new={is_new_study_series} is_same={is_same_series} | "
            f"rescale_slope={rescale_slope} rescale_intercept={rescale_intercept} | "
            f"use_rescaled_values={use_rescaled_values}"
        )

    # -- 4. New study/series W/L resolution ----------------------------------
    if is_new_study_series:
        window_center = None
        window_width = None
        stored_window_center: float | None = None
        stored_window_width: float | None = None

        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_in_dict = bool(
            study_uid and new_series_uid and current_studies
            and study_uid in current_studies
            and new_series_uid in current_studies[study_uid]
        )
        if DEBUG_WL:
            print(
                f"[DEBUG-WL] new series: series_in_current_studies={series_in_dict} "
                f"(study_uid in current_studies={study_uid in current_studies if current_studies else False} "
                f"series_uid in study={new_series_uid in current_studies.get(study_uid, {}) if study_uid and current_studies else False})"
            )

        if study_uid and new_series_uid and current_studies:
            if study_uid in current_studies and new_series_uid in current_studies[study_uid]:
                series_datasets = current_studies[study_uid][new_series_uid]

                # 4a. Compute series pixel range
                _, _, series_pixel_min, series_pixel_max = _compute_pixel_range_wl(
                    mgr, dataset, series_datasets, use_rescaled_values
                )

                # 4b. Build presets and extract embedded W/L
                wc, ww, is_rescaled = _build_presets_and_extract_wl(
                    mgr, dataset, rescale_slope, rescale_intercept, "embedded"
                )

                # 4c. Determine stored W/L
                if wc is not None and ww is not None:
                    # Embedded W/L found -- apply rescale conversion
                    stored_window_center, stored_window_width = _apply_rescale_and_store_defaults(
                        mgr, wc, ww, is_rescaled, use_rescaled_values,
                        rescale_slope, rescale_intercept, "",
                    )
                    if DEBUG_WL:
                        print(f"[DEBUG-WL] after conversion stored_wc={stored_window_center} stored_ww={stored_window_width}")
                elif series_pixel_min is not None and series_pixel_max is not None:
                    # No embedded W/L but pixel range available
                    stored_window_center, stored_window_width = _compute_wl_from_series_pixel_range(
                        mgr, series_datasets, series_pixel_min, series_pixel_max,
                        use_rescaled_values,
                    )
                else:
                    # Single-slice pixel range fallback
                    stored_window_center, stored_window_width = _compute_wl_from_single_slice(
                        mgr, dataset, use_rescaled_values
                    )
                mgr.view_state_manager.window_level_user_modified = False

        if stored_window_center is not None and stored_window_width is not None:
            if DEBUG_WL:
                study_uid = getattr(dataset, 'StudyInstanceUID', '')
                print(
                    f"[DEBUG-WL] New series WL: study_uid={study_uid[:20] if study_uid else ''}... "
                    f"series_uid={new_series_uid[:20] if new_series_uid else ''}... "
                    f"use_rescaled={use_rescaled_values} slope={rescale_slope} intercept={rescale_intercept} "
                    f"stored_wc={stored_window_center} stored_ww={stored_window_width}"
                )
            window_center = stored_window_center
            window_width = stored_window_width
            _store_wl_and_defaults(
                mgr, window_center, window_width, use_rescaled_values, series_identifier
            )
        else:
            # -- Fallback branch: series not in dict or no stored W/L --------
            if DEBUG_WL:
                study_uid = getattr(dataset, 'StudyInstanceUID', '')
                print(
                    f"[DEBUG-WL] New series WL fallback: study_uid={study_uid[:20] if study_uid else ''}... "
                    f"series_uid={new_series_uid[:20] if new_series_uid else ''}... "
                    f"computing from dataset being loaded"
                )
            # Compute single-dataset pixel range for the fallback path
            try:
                pixel_min, pixel_max = mgr.dicom_processor.get_pixel_value_range(
                    dataset, apply_rescale=use_rescaled_values
                )
                if pixel_min is not None and pixel_max is not None:
                    mgr.view_state_manager.set_series_pixel_range(pixel_min, pixel_max)
                else:
                    mgr.view_state_manager.clear_series_pixel_range()
            except Exception:
                mgr.view_state_manager.clear_series_pixel_range()

            # Build presets and extract W/L (same logic as branch A)
            wc, ww, is_rescaled = _build_presets_and_extract_wl(
                mgr, dataset, rescale_slope, rescale_intercept, "fallback"
            )

            if wc is not None and ww is not None:
                wc, ww = _apply_rescale_and_store_defaults(
                    mgr, wc, ww, is_rescaled, use_rescaled_values,
                    rescale_slope, rescale_intercept, "fallback",
                )
                window_center = wc
                window_width = ww
                mgr.view_state_manager.current_window_center = wc
                mgr.view_state_manager.current_window_width = ww
                if series_identifier not in mgr.view_state_manager.series_defaults:
                    mgr.view_state_manager.series_defaults[series_identifier] = {}
                mgr.view_state_manager.series_defaults[series_identifier].update({
                    'window_center': window_center,
                    'window_width': window_width,
                    'use_rescaled_values': use_rescaled_values,
                    'image_inverted': mgr.image_viewer.image_inverted,
                    'window_level_defaults_set': True,
                })
            else:
                if DEBUG_WL:
                    print("[DEBUG-WL] fallback: no embedded WL (wc/ww None), dataset_to_image will use internal default")
                window_center = None
                window_width = None
                mgr.view_state_manager.current_window_center = None
                mgr.view_state_manager.current_window_width = None

        # -- 5. Restore user W/L cache if available --------------------------
        cached_wc, cached_ww = _restore_user_wl_cache(mgr, series_identifier)
        if cached_wc is not None:
            window_center = cached_wc
            window_width = cached_ww

    return window_center, window_width, use_rescaled_values
