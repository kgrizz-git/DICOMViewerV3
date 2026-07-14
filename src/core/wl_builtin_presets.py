"""
Built-in window/level presets per DICOM modality.

Clinical starting points for common review — not a replacement for PACS-specific presets.
Each entry is ``(center, width, is_rescaled, name)``.

``is_rescaled=True`` — values in calibrated units (HU for CT, SUV for PT when rescale applies).
``is_rescaled=False`` — values in raw stored pixel space (typical MR without rescale tags).

Modality codes follow DICOM (CT, MR, PT, CR, DX, MG, US, NM, RF, …).
``ANY`` is used when the series modality is unknown or has no dedicated table.
"""


WLPreset = tuple[float, float, bool, str | None]  # (center, width, is_rescaled, name)

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
    # Raw 12-bit-style display ranges (default when MR has no rescale tags).
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
    "CR": [
        (-600.0, 1500.0, True, "Chest"),
        (300.0, 1500.0, True, "Bone"),
        (2048.0, 4096.0, False, "Default (raw)"),
    ],
    "DX": [
        (-600.0, 1500.0, True, "Chest"),
        (300.0, 1500.0, True, "Bone"),
        (2048.0, 4096.0, False, "Default (raw)"),
    ],
    "MG": [
        (2048.0, 4096.0, False, "Default"),
    ],
    "NM": [
        (500.0, 1000.0, True, "Default"),
        (128.0, 256.0, False, "Default (raw)"),
    ],
    "US": [
        (128.0, 256.0, False, "Default"),
    ],
    "RF": [
        (2048.0, 4096.0, False, "Fluoro"),
    ],
    "XA": [
        (2048.0, 4096.0, False, "Fluoro"),
    ],
    "ANY": [
        (128.0, 256.0, False, "Auto-range fallback"),
        (512.0, 1024.0, False, "Wide"),
    ],
}

# Appended to MR built-ins only when RescaleSlope/Intercept are present on the series.
MR_HU_PRESETS: list[WLPreset] = [
    (300.0, 600.0, True, "Brain T1 (HU)"),
    (400.0, 800.0, True, "Brain T2 (HU)"),
    (400.0, 800.0, True, "Spine (HU)"),
]


def get_builtin_presets(modality: str | None) -> list[WLPreset]:
    """
    Return built-in presets for *modality* (case-insensitive).

    Unknown or empty modality uses the ``ANY`` table. Known modalities do not
    include ``ANY`` entries (only their dedicated list).
    """
    if not modality or not str(modality).strip():
        return list(BUILTIN_PRESETS.get("ANY", []))
    key = str(modality).upper().strip()
    if key in BUILTIN_PRESETS and key != "ANY":
        return list(BUILTIN_PRESETS[key])
    return list(BUILTIN_PRESETS.get("ANY", []))


def get_mr_hu_builtin_presets() -> list[WLPreset]:
    """HU-space MR presets when rescale tags are available on the series."""
    return list(MR_HU_PRESETS)
