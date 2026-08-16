"""
Built-in window/level presets per DICOM modality.

Clinical starting points for common review — not a replacement for PACS-specific presets.
Each entry is ``(center, width, is_rescaled, name)``.

``is_rescaled=True`` — values in calibrated units (HU for CT, SUV for PT when rescale applies).
``is_rescaled=False`` — values in raw stored pixel space (typical MR without rescale tags).

Modality codes follow DICOM (CT, MR, PT, CR, DX, MG, US, NM, RF, …).
``ANY`` is used when the series modality is unknown or has no dedicated table.

Bit-depth-aware presets: CR/DX/MG/NM/RF/XA/US/ANY derive ``Default`` and ``Wide``
from the dataset's stored pixel range (``BitsStored``/``BitsAllocated``/``PixelRepresentation``)
when a dataset is provided. Without a dataset, a 16-bit unsigned fallback is used.
"""

from __future__ import annotations

from typing import Any

from core.dicom_pixel_range import get_stored_value_range

WLPreset = tuple[float, float, bool, str | None]  # (center, width, is_rescaled, name)

_FALLBACK_BITS_ALLOCATED = 16

BUILTIN_PRESETS: dict[str, list[WLPreset]] = {
    "CT": [
        (40.0, 400.0, True, "Abdomen"),
        (300.0, 1500.0, True, "Bone"),
        (40.0, 80.0, True, "Brain"),
        (-600.0, 1500.0, True, "Lung"),
        (50.0, 350.0, True, "Mediastinum"),
        (60.0, 400.0, True, "Soft Tissue"),
        (30.0, 300.0, True, "Spine"),
        (60.0, 150.0, True, "Liver"),
        (60.0, 450.0, True, "Head & Neck"),
        (40.0, 400.0, True, "Pelvis"),
        (400.0, 2000.0, True, "Temporal Bone"),
    ],
    "MR": [
        (500.0, 1000.0, False, "Brain T1"),
        (400.0, 1200.0, False, "Brain T2"),
        (450.0, 1000.0, False, "Spine"),
        (300.0, 800.0, False, "Knee"),
        (350.0, 900.0, False, "Shoulder"),
    ],
    "PT": [
        (2.5, 5.0, True, "SUV 0–5"),
        (5.0, 10.0, True, "SUV 0–10"),
    ],
}

_RAW_PRESET_MODALITIES = ("CR", "DX", "MG", "NM", "US", "RF", "XA", "ANY")

MR_HU_PRESETS: list[WLPreset] = [
    (300.0, 600.0, True, "Brain T1 (HU)"),
    (400.0, 800.0, True, "Brain T2 (HU)"),
    (400.0, 800.0, True, "Spine (HU)"),
]

_CR_DX_HU_GATED: list[WLPreset] = [
    (-600.0, 1500.0, True, "Chest"),
    (300.0, 1500.0, True, "Bone"),
]

_NM_HU_GATED: list[WLPreset] = [
    # Preserve NM's established calibrated-space starting window.  It is only
    # offered when a usable rescale exists (see wl_preset_catalog), so a zero
    # width placeholder can never reach the W/L renderer.
    (500.0, 1000.0, True, "rescaled Default"),
]


def _presets_from_stored_range(
    stored_min: float,
    stored_max: float,
    *,
    default_name: str = "Default",
    wide_name: str = "Wide",
) -> list[WLPreset]:
    """Generate Default (full range) and Wide (1.5× range) presets from stored pixel range."""
    range_width = stored_max - stored_min
    center = (stored_min + stored_max) / 2.0
    default_width = range_width
    wide_width = 1.5 * range_width
    return [
        (center, default_width, False, default_name),
        (center, wide_width, False, wide_name),
    ]


def _fallback_stored_range() -> tuple[float, float]:
    """Tag-independent fallback range: 16-bit unsigned (0 .. 65535)."""
    return (0.0, float(2**_FALLBACK_BITS_ALLOCATED - 1))


def get_builtin_presets(
    modality: str | None,
    dataset: Any | None = None,
) -> list[WLPreset]:
    """Return built-in presets for *modality* (case-insensitive).

    When *dataset* is provided and *modality* is one of CR/DX/MG/NM/RF/XA/US/ANY,
    presets are derived from the dataset's stored pixel range (bit-depth-aware).
    Without a dataset, a 16-bit unsigned fallback range is used.

    Unknown or empty modality uses the ``ANY`` table.
    """
    if not modality or not str(modality).strip():
        key = "ANY"
    else:
        key = str(modality).upper().strip()

    if key in ("CT", "MR", "PT"):
        return list(BUILTIN_PRESETS.get(key, []))

    if key not in _RAW_PRESET_MODALITIES:
        key = "ANY"

    if dataset is not None:
        try:
            stored_min, stored_max = get_stored_value_range(dataset)
        except Exception:
            stored_min, stored_max = _fallback_stored_range()
    else:
        stored_min, stored_max = _fallback_stored_range()

    if key == "NM":
        default_name = "Default"
        wide_name = "Wide"
    elif key in ("RF", "XA"):
        default_name = "Fluoro"
        wide_name = "Fluoro Wide"
    elif key == "ANY":
        default_name = "Default"
        wide_name = "Wide"
    else:
        default_name = "Default"
        wide_name = "Wide"

    return _presets_from_stored_range(stored_min, stored_max, default_name=default_name, wide_name=wide_name)


def get_mr_hu_builtin_presets() -> list[WLPreset]:
    """HU-space MR presets when rescale tags are available on the series."""
    return list(MR_HU_PRESETS)


def get_hu_gated_builtin_presets(modality: str) -> list[WLPreset]:
    """HU-gated presets for CR/DX (Chest/Bone) and NM (rescaled Default).

    These presets are only valid when a real rescale (``RescaleSlope``/``RescaleIntercept``)
    is present on the dataset, so they convert correctly from HU to raw.
    """
    key = modality.upper().strip() if modality else ""
    if key in ("CR", "DX"):
        return list(_CR_DX_HU_GATED)
    if key == "NM":
        return list(_NM_HU_GATED)
    return []
