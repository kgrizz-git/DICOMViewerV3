"""
Window/level preset catalog: merge DICOM, built-in, and user presets with labeling helpers.

Inputs:
    - pydicom Dataset, DICOMProcessor, ConfigManager (display_config)
Outputs:
    - Ordered ``WindowLevelPreset`` list and legacy 4-tuples for ViewStateManager
    - Menu labels and tooltips (unit-aware; display C/W match viewer raw/rescaled mode)

Requirements:
    - ``core.wl_builtin_presets``, ``core.dicom_window_level`` (via DICOMProcessor)
"""

from __future__ import annotations

from typing import Any, Literal, NamedTuple

from pydicom.dataset import Dataset

from core.dicom_window_level import (
    convert_window_level_raw_to_rescaled,
    convert_window_level_rescaled_to_raw,
)
from core.wl_builtin_presets import get_builtin_presets, get_mr_hu_builtin_presets

PresetSource = Literal["dicom", "builtin", "user"]

LegacyWLPreset = tuple[float, float, bool, str | None]


class WindowLevelPreset(NamedTuple):
    """Single W/L preset with source metadata for grouped menus."""

    center: float
    width: float
    is_rescaled: bool
    name: str | None
    source: PresetSource
    modality: str | None = None

    def to_legacy_tuple(self) -> LegacyWLPreset:
        """Convert to ``(center, width, is_rescaled, name)`` for ViewStateManager."""
        return (self.center, self.width, self.is_rescaled, self.name)


def presets_to_legacy(presets: list[WindowLevelPreset]) -> list[LegacyWLPreset]:
    """Convert a preset list to legacy tuples."""
    return [p.to_legacy_tuple() for p in presets]


def filter_user_preset_dicts(
    user_entries: list[dict[str, Any]],
    modality: str,
) -> list[WindowLevelPreset]:
    """
    Filter user config presets for *modality* (``ANY`` matches all).

    Each dict uses keys: name, modality, center, width, is_rescaled.
    """
    mod_upper = modality.upper().strip() if modality else ""
    result: list[WindowLevelPreset] = []
    for entry in user_entries:
        pm = (entry.get("modality") or "ANY").upper()
        if pm not in ("ANY", mod_upper):
            continue
        result.append(
            WindowLevelPreset(
                center=float(entry["center"]),
                width=float(entry["width"]),
                is_rescaled=bool(entry.get("is_rescaled", True)),
                name=str(entry.get("name", "Custom")),
                source="user",
                modality=pm if pm != "ANY" else "ANY",
            )
        )
    return result


def build_preset_list(
    dataset: Dataset,
    dicom_processor: Any,
    config_manager: Any,
    *,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> list[WindowLevelPreset]:
    """
    Build merged preset list: DICOM tags, built-in (modality + optional MR HU), then user.

    Args:
        dataset: Current slice dataset (for Modality and DICOM WC/WW).
        dicom_processor: ``DICOMProcessor`` instance.
        config_manager: Config manager with ``get_wl_user_presets()``.
        rescale_slope: Optional rescale slope for DICOM preset interpretation.
        rescale_intercept: Optional rescale intercept for DICOM preset interpretation.
    """
    dicom_tuples = dicom_processor.get_window_level_presets_from_dataset(
        dataset,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
    )
    dicom_presets = [
        WindowLevelPreset(
            center=wc,
            width=ww,
            is_rescaled=is_rescaled,
            name=name if name else "From DICOM",
            source="dicom",
            modality=str(getattr(dataset, "Modality", "") or "").upper() or None,
        )
        for wc, ww, is_rescaled, name in dicom_tuples
    ]

    modality = str(getattr(dataset, "Modality", "") or "")
    builtin_tuples = get_builtin_presets(modality)
    if modality.upper() == "MR" and _has_usable_rescale(rescale_slope, rescale_intercept):
        builtin_tuples = list(builtin_tuples) + get_mr_hu_builtin_presets()

    builtin_presets = [
        WindowLevelPreset(
            center=wc,
            width=ww,
            is_rescaled=is_rescaled,
            name=name,
            source="builtin",
            modality=modality.upper().strip() or None,
        )
        for wc, ww, is_rescaled, name in builtin_tuples
    ]

    user_presets: list[WindowLevelPreset] = []
    if config_manager is not None and hasattr(config_manager, "get_wl_user_presets"):
        user_presets = filter_user_preset_dicts(
            config_manager.get_wl_user_presets(),
            modality,
        )

    return dicom_presets + builtin_presets + user_presets


def _has_usable_rescale(
    rescale_slope: float | None,
    rescale_intercept: float | None,
) -> bool:
    return (
        rescale_slope is not None
        and rescale_intercept is not None
        and rescale_slope != 0.0  # NOSONAR(S1244): RescaleSlope is DICOM DS-VR; exact 0.0 is well-defined
    )


def storage_space_label(
    preset: WindowLevelPreset,
    *,
    unit: str | None = None,
) -> str | None:
    """Short label for the value space the preset is stored in (HU, raw, etc.)."""
    if not preset.is_rescaled:
        return "raw"
    if unit and unit.upper() not in ("", "UNSPECIFIED", "US"):
        return unit
    return None


def _format_wl_number(value: float) -> str:
    """Format center/width for menus: integers without decimals, else one decimal."""
    rounded = round(value)
    if abs(value - rounded) < 1e-6:
        return str(int(rounded))
    return f"{value:.1f}"


def _preset_values_differ_after_viewer_conversion(
    preset: WindowLevelPreset,
    *,
    use_rescaled: bool,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> bool:
    """True when stored C/W differ from viewer-space display (conversion applies)."""
    if preset.is_rescaled == use_rescaled:
        return False
    if preset.is_rescaled and not use_rescaled:
        return _has_usable_rescale(rescale_slope, rescale_intercept)
    return rescale_slope is not None and rescale_intercept is not None


def format_preset_display_values(
    preset: WindowLevelPreset,
    *,
    use_rescaled: bool,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> tuple[float, float]:
    """
    Return center/width in the viewer's current raw vs rescaled mode.

    Uses the same conversion rules as ``window_level_preset_handler`` / ``ViewStateManager``.
    """
    wc, ww = preset.center, preset.width
    if preset.is_rescaled and not use_rescaled:
        if _has_usable_rescale(rescale_slope, rescale_intercept):
            assert rescale_slope is not None and rescale_intercept is not None
            wc, ww = convert_window_level_rescaled_to_raw(
                wc, ww, rescale_slope, rescale_intercept
            )
    elif not preset.is_rescaled and use_rescaled:
        if rescale_slope is not None and rescale_intercept is not None:
            wc, ww = convert_window_level_raw_to_rescaled(
                wc, ww, rescale_slope, rescale_intercept
            )
    return wc, ww


def _format_preset_name_base(
    preset: WindowLevelPreset,
    *,
    unit: str | None = None,
) -> str:
    """Name and storage-space suffix only (unit rules from DICOM labels plan)."""
    name = preset.name or "Preset"
    space = storage_space_label(preset, unit=unit)
    suffix = f" ({space})" if space else ""
    if preset.source == "dicom":
        return f"{name}{suffix}"
    if preset.source == "user" and preset.modality:
        mod = preset.modality
        if mod != "ANY":
            if space:
                return f"{name} ({mod}, {space})"
            return f"{name} ({mod})"
    return f"{name}{suffix}"


def format_preset_menu_wl_compact(disp_center: float, disp_width: float) -> str:
    """Compact viewer-space W/L suffix for menu labels, e.g. `` (W 400/C 40)``."""
    return (
        f" (W {_format_wl_number(disp_width)}/C {_format_wl_number(disp_center)})"
    )


def format_status_bar_wl(
    center: float,
    width: float,
    *,
    unit: str | None = None,
) -> str:
    """
    Status-bar W/L segment: compact ``(W …/C …)`` plus optional unit suffix.

    Never includes preset names — only numeric center/width in viewer space.
    """
    wl_part = format_preset_menu_wl_compact(center, width).strip()
    if unit and unit.upper() not in ("", "UNSPECIFIED", "US"):
        return f"{wl_part} ({unit})"
    return wl_part


def format_preset_menu_label(
    preset: WindowLevelPreset,
    *,
    unit: str | None = None,
    use_rescaled: bool = False,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> str:
    """
    Menu text: preset name (with unit/storage suffix) plus viewer-space W/L.

    Width is shown before center, e.g. ``Lung (HU) (W 400/C 40)``.
    """
    base = _format_preset_name_base(preset, unit=unit)
    disp_c, disp_w = format_preset_display_values(
        preset,
        use_rescaled=use_rescaled,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
    )
    return f"{base}{format_preset_menu_wl_compact(disp_c, disp_w)}"


def format_preset_tooltip(
    preset: WindowLevelPreset,
    *,
    unit: str | None = None,
    use_rescaled: bool,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> str:
    """Full detail for QAction tooltips."""
    space = storage_space_label(preset, unit=unit)
    disp_c, disp_w = format_preset_display_values(
        preset,
        use_rescaled=use_rescaled,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
    )
    lines = [
        f"Center {_format_wl_number(disp_c)}, Width {_format_wl_number(disp_w)}",
    ]
    if _preset_values_differ_after_viewer_conversion(
        preset,
        use_rescaled=use_rescaled,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
    ):
        stored_space = space or ("rescaled" if preset.is_rescaled else "raw")
        lines.append(
            f"Stored: Center {_format_wl_number(preset.center)}, "
            f"Width {_format_wl_number(preset.width)} ({stored_space})"
        )
    elif space:
        lines.append(f"Stored as {space}")
    else:
        lines.append("Stored as rescaled values")
    if preset.source == "dicom":
        lines.append("From DICOM WindowCenter / WindowWidth (0018,1050 / 1051)")
    elif preset.source == "builtin":
        mod = preset.modality or "general"
        lines.append(f"Built-in preset for {mod}")
    elif preset.source == "user":
        mod = preset.modality or "ANY"
        lines.append(f"Custom preset (modality filter: {mod})")

    viewer_mode = "rescaled" if use_rescaled else "raw"
    lines.append(f"Viewer mode: {viewer_mode}")
    if _preset_values_differ_after_viewer_conversion(
        preset,
        use_rescaled=use_rescaled,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
    ):
        lines.append("Values convert automatically when applied in the current viewer mode.")
    return "\n".join(lines)


def format_preset_status_name(
    preset: WindowLevelPreset,
    *,
    unit: str | None = None,
) -> str:
    """Status bar text after applying a preset (e.g. ``Lung (HU)``)."""
    name = preset.name or "Default"
    space = storage_space_label(preset, unit=unit)
    if space:
        return f"{name} ({space})"
    return name
