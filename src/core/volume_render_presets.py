"""
Volume render transfer-function presets.

All built-in ``TransferFunctionPreset`` definitions, modality grouping, and
the flat ``BUILTIN_PRESETS`` list.  Extracted from ``volume_renderer.py`` to
keep preset data separate from VTK pipeline code.

Callers may import from here directly or from ``volume_renderer`` (which
re-exports everything for backward compatibility).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass


@dataclass
class TransferFunctionPreset:
    """
    Defines a volume-rendering transfer function.

    Attributes:
        name: Human-readable preset name.
        scalar_opacity: Control points ``(scalar_value, opacity)`` for the
            piecewise scalar opacity function.
        color: Control points ``(scalar_value, r, g, b)`` for the colour
            transfer function.
        gradient_opacity: Optional control points ``(gradient_mag, opacity)``
            for gradient-based opacity.
    """

    name: str
    scalar_opacity: list[tuple[float, float]]
    color: list[tuple[float, float, float, float]]
    gradient_opacity: list[tuple[float, float]] | None = None


# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------

PRESET_CT_BONE = TransferFunctionPreset(
    name="CT Bone",
    scalar_opacity=[
        (-1000.0, 0.0),
        (150.0, 0.0),
        (200.0, 0.05),
        (400.0, 0.4),
        (1000.0, 0.8),
        (3000.0, 1.0),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (150.0, 0.0, 0.0, 0.0),
        (200.0, 0.85, 0.75, 0.55),
        (400.0, 0.95, 0.92, 0.82),
        (1000.0, 1.0, 1.0, 0.95),
        (3000.0, 1.0, 1.0, 1.0),
    ],
    gradient_opacity=[
        (0.0, 0.10),
        (30.0, 0.35),
        (90.0, 0.75),
        (200.0, 1.0),
    ],
)

PRESET_CT_SOFT_TISSUE = TransferFunctionPreset(
    name="CT Soft Tissue",
    scalar_opacity=[
        (-1000.0, 0.0),
        (-100.0, 0.0),
        (-50.0, 0.02),
        (50.0, 0.15),
        (200.0, 0.35),
        (300.0, 0.6),
        (1000.0, 0.8),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (-100.0, 0.0, 0.0, 0.0),
        (-50.0, 0.55, 0.25, 0.15),
        (50.0, 0.88, 0.60, 0.50),
        (200.0, 0.92, 0.80, 0.70),
        (300.0, 0.95, 0.92, 0.82),
        (1000.0, 1.0, 1.0, 0.95),
    ],
    gradient_opacity=[
        (0.0, 0.10),
        (15.0, 0.25),
        (60.0, 0.65),
        (150.0, 1.0),
    ],
)

PRESET_CT_LUNG = TransferFunctionPreset(
    name="CT Lung",
    scalar_opacity=[
        (-1000.0, 0.0),
        (-900.0, 0.0),
        (-800.0, 0.15),
        (-500.0, 0.05),
        (-200.0, 0.0),
        (100.0, 0.0),
        (300.0, 0.3),
        (1000.0, 0.7),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (-900.0, 0.10, 0.15, 0.35),
        (-800.0, 0.25, 0.35, 0.55),
        (-500.0, 0.40, 0.50, 0.65),
        (-200.0, 0.55, 0.25, 0.15),
        (100.0, 0.88, 0.60, 0.50),
        (300.0, 0.95, 0.92, 0.82),
        (1000.0, 1.0, 1.0, 0.95),
    ],
    gradient_opacity=[
        (0.0, 0.10),
        (20.0, 0.30),
        (80.0, 0.70),
        (200.0, 1.0),
    ],
)

PRESET_MR_DEFAULT = TransferFunctionPreset(
    name="MR Default",
    scalar_opacity=[
        (0.0, 0.0),
        (100.0, 0.0),
        (200.0, 0.05),
        (500.0, 0.20),
        (1000.0, 0.40),
        (2000.0, 0.60),
        (4000.0, 0.80),
    ],
    color=[
        (0.0, 0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0, 0.0),
        (200.0, 0.30, 0.30, 0.30),
        (500.0, 0.55, 0.55, 0.55),
        (1000.0, 0.75, 0.75, 0.75),
        (2000.0, 0.90, 0.90, 0.90),
        (4000.0, 1.0, 1.0, 1.0),
    ],
    gradient_opacity=[
        (0.0, 0.10),
        (20.0, 0.30),
        (60.0, 0.65),
        (150.0, 1.0),
    ],
)

PRESET_CT_MUSCLE = TransferFunctionPreset(
    name="CT Muscle",
    scalar_opacity=[
        (-1000.0, 0.0),
        (-50.0, 0.0),
        (0.0, 0.02),
        (40.0, 0.12),
        (80.0, 0.30),
        (150.0, 0.50),
        (300.0, 0.70),
        (1000.0, 0.85),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (-50.0, 0.0, 0.0, 0.0),
        (0.0, 0.45, 0.20, 0.15),
        (40.0, 0.70, 0.35, 0.25),
        (80.0, 0.85, 0.50, 0.40),
        (150.0, 0.90, 0.70, 0.60),
        (300.0, 0.95, 0.90, 0.80),
        (1000.0, 1.0, 1.0, 0.95),
    ],
)

PRESET_CT_ANGIO = TransferFunctionPreset(
    name="CT Angiography",
    scalar_opacity=[
        (-1000.0, 0.0),
        (100.0, 0.0),
        (150.0, 0.05),
        (200.0, 0.30),
        (300.0, 0.60),
        (500.0, 0.80),
        (1000.0, 0.90),
        (3000.0, 1.0),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0, 0.0),
        (150.0, 0.55, 0.15, 0.15),
        (200.0, 0.80, 0.20, 0.15),
        (300.0, 0.90, 0.30, 0.20),
        (500.0, 0.95, 0.85, 0.75),
        (1000.0, 1.0, 1.0, 0.95),
        (3000.0, 1.0, 1.0, 1.0),
    ],
)

PRESET_CT_FAT = TransferFunctionPreset(
    name="CT Fat",
    scalar_opacity=[
        (-1000.0, 0.0),
        (-200.0, 0.0),
        (-150.0, 0.05),
        (-100.0, 0.30),
        (-50.0, 0.50),
        (0.0, 0.15),
        (100.0, 0.05),
        (300.0, 0.0),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (-200.0, 0.0, 0.0, 0.0),
        (-150.0, 0.90, 0.80, 0.30),
        (-100.0, 0.95, 0.85, 0.40),
        (-50.0, 1.0, 0.90, 0.50),
        (0.0, 0.88, 0.60, 0.50),
        (100.0, 0.55, 0.25, 0.15),
        (300.0, 0.0, 0.0, 0.0),
    ],
)

PRESET_CT_SKIN = TransferFunctionPreset(
    name="CT Skin",
    scalar_opacity=[
        (-1000.0, 0.0),
        (-500.0, 0.0),
        (-200.0, 0.0),
        (-100.0, 0.15),
        (0.0, 0.20),
        (100.0, 0.10),
        (200.0, 0.02),
        (500.0, 0.0),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (-500.0, 0.0, 0.0, 0.0),
        (-200.0, 0.0, 0.0, 0.0),
        (-100.0, 0.85, 0.70, 0.55),
        (0.0, 0.92, 0.78, 0.65),
        (100.0, 0.88, 0.72, 0.58),
        (200.0, 0.80, 0.65, 0.50),
        (500.0, 0.0, 0.0, 0.0),
    ],
)

PRESET_MR_T1_BRAIN = TransferFunctionPreset(
    name="MR T1 Brain",
    scalar_opacity=[
        (0.0, 0.0),
        (50.0, 0.0),
        (100.0, 0.02),
        (200.0, 0.10),
        (400.0, 0.25),
        (600.0, 0.40),
        (800.0, 0.55),
        (1200.0, 0.70),
    ],
    color=[
        (0.0, 0.0, 0.0, 0.0),
        (50.0, 0.0, 0.0, 0.0),
        (100.0, 0.20, 0.20, 0.25),
        (200.0, 0.40, 0.35, 0.40),
        (400.0, 0.60, 0.55, 0.55),
        (600.0, 0.75, 0.70, 0.70),
        (800.0, 0.88, 0.82, 0.80),
        (1200.0, 1.0, 0.95, 0.92),
    ],
)

PRESET_MR_T2_BRAIN = TransferFunctionPreset(
    name="MR T2 Brain",
    scalar_opacity=[
        (0.0, 0.0),
        (100.0, 0.0),
        (250.0, 0.04),
        (600.0, 0.18),
        (1000.0, 0.32),
        (1500.0, 0.48),
        (2500.0, 0.65),
        (3500.0, 0.82),
    ],
    color=[
        (0.0, 0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0, 0.0),
        (250.0, 0.18, 0.18, 0.28),
        (600.0, 0.40, 0.42, 0.52),
        (1000.0, 0.58, 0.60, 0.68),
        (1500.0, 0.72, 0.72, 0.80),
        (2500.0, 0.85, 0.85, 0.92),
        (3500.0, 0.95, 0.95, 1.0),
    ],
    gradient_opacity=[
        (0.0, 0.10),
        (20.0, 0.30),
        (60.0, 0.70),
        (150.0, 1.0),
    ],
)

PRESET_MR_MRA = TransferFunctionPreset(
    name="MR Angiography",
    scalar_opacity=[
        (0.0, 0.0),
        (150.0, 0.0),
        (300.0, 0.04),
        (550.0, 0.25),
        (800.0, 0.60),
        (1200.0, 0.80),
        (2500.0, 0.92),
    ],
    color=[
        (0.0, 0.0, 0.0, 0.0),
        (150.0, 0.0, 0.0, 0.0),
        (300.0, 0.50, 0.10, 0.10),
        (550.0, 0.85, 0.25, 0.20),
        (800.0, 0.92, 0.60, 0.55),
        (1200.0, 0.96, 0.88, 0.85),
        (2500.0, 1.0, 1.0, 0.98),
    ],
)

PRESET_CT_SMOOTH_ANATOMY = TransferFunctionPreset(
    name="CT Smooth Anatomy",
    scalar_opacity=[
        (-1000.0, 0.0),
        (-200.0, 0.0),
        (-50.0, 0.01),
        (50.0, 0.06),
        (200.0, 0.15),
        (400.0, 0.30),
        (800.0, 0.50),
        (1500.0, 0.65),
        (3000.0, 0.75),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (-200.0, 0.0, 0.0, 0.0),
        (-50.0, 0.45, 0.25, 0.18),
        (50.0, 0.70, 0.50, 0.40),
        (200.0, 0.85, 0.70, 0.58),
        (400.0, 0.90, 0.82, 0.72),
        (800.0, 0.95, 0.90, 0.85),
        (1500.0, 0.98, 0.95, 0.92),
        (3000.0, 1.0, 1.0, 1.0),
    ],
)

PRESET_PT_DEFAULT = TransferFunctionPreset(
    name="PT Default (counts)",
    scalar_opacity=[
        (0.0, 0.0),
        (50.0, 0.0),
        (200.0, 0.03),
        (1000.0, 0.15),
        (3000.0, 0.35),
        (6000.0, 0.55),
        (10000.0, 0.75),
        (20000.0, 0.90),
    ],
    color=[
        (0.0, 0.0, 0.0, 0.0),
        (50.0, 0.0, 0.0, 0.0),
        (200.0, 0.0, 0.0, 0.35),
        (1000.0, 0.0, 0.30, 0.65),
        (3000.0, 0.10, 0.65, 0.45),
        (6000.0, 0.70, 0.80, 0.10),
        (10000.0, 0.95, 0.55, 0.10),
        (20000.0, 1.0, 0.15, 0.05),
    ],
)

PRESET_NM_DEFAULT = TransferFunctionPreset(
    name="NM Default (counts)",
    scalar_opacity=[
        (0.0, 0.0),
        (20.0, 0.0),
        (100.0, 0.03),
        (500.0, 0.12),
        (1500.0, 0.30),
        (3000.0, 0.50),
        (5000.0, 0.70),
        (10000.0, 0.85),
    ],
    color=[
        (0.0, 0.0, 0.0, 0.0),
        (20.0, 0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0, 0.40),
        (500.0, 0.0, 0.35, 0.70),
        (1500.0, 0.20, 0.70, 0.50),
        (3000.0, 0.75, 0.85, 0.15),
        (5000.0, 0.95, 0.60, 0.10),
        (10000.0, 1.0, 0.20, 0.05),
    ],
)

PRESET_GENERIC_INTENSITY = TransferFunctionPreset(
    name="Generic Intensity",
    scalar_opacity=[
        (0.0, 0.0),
        (50.0, 0.0),
        (200.0, 0.04),
        (500.0, 0.12),
        (1000.0, 0.28),
        (2000.0, 0.50),
        (4000.0, 0.72),
        (8000.0, 0.88),
    ],
    color=[
        (0.0, 0.0, 0.0, 0.0),
        (50.0, 0.0, 0.0, 0.0),
        (200.0, 0.25, 0.25, 0.30),
        (500.0, 0.45, 0.45, 0.50),
        (1000.0, 0.60, 0.60, 0.65),
        (2000.0, 0.75, 0.75, 0.78),
        (4000.0, 0.88, 0.88, 0.90),
        (8000.0, 1.0, 1.0, 1.0),
    ],
)

PRESET_CT_ANATOMY_COLORS = TransferFunctionPreset(
    name="CT Anatomy (false color)",
    scalar_opacity=[
        (-1000.0, 0.0),
        (-900.0, 0.0),
        (-600.0, 0.06),
        (-200.0, 0.0),
        (-150.0, 0.05),
        (-80.0, 0.22),
        (-40.0, 0.15),
        (0.0, 0.0),
        (20.0, 0.18),
        (80.0, 0.25),
        (150.0, 0.0),
        (200.0, 0.35),
        (500.0, 0.65),
        (1000.0, 0.85),
        (3000.0, 1.0),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (-900.0, 0.08, 0.14, 0.35),
        (-600.0, 0.20, 0.40, 0.65),
        (-200.0, 0.15, 0.30, 0.55),
        (-150.0, 0.90, 0.75, 0.05),
        (-80.0,  0.95, 0.82, 0.08),
        (-40.0,  0.85, 0.60, 0.30),
        (0.0,    0.75, 0.35, 0.30),
        (20.0,   0.85, 0.35, 0.35),
        (80.0,   0.80, 0.15, 0.15),
        (150.0,  0.70, 0.20, 0.20),
        (200.0,  0.88, 0.78, 0.60),
        (500.0,  0.95, 0.90, 0.80),
        (1000.0, 1.00, 1.00, 0.96),
        (3000.0, 1.00, 1.00, 1.00),
    ],
)

PRESET_CT_VIVID_ANGIO = TransferFunctionPreset(
    name="CT Angio (vivid)",
    scalar_opacity=[
        (-1000.0, 0.0),
        (100.0,   0.0),
        (130.0,   0.02),
        (160.0,   0.40),
        (250.0,   0.70),
        (400.0,   0.0),
        (600.0,   0.55),
        (1000.0,  0.85),
        (3000.0,  1.0),
    ],
    color=[
        (-1000.0, 0.0, 0.0, 0.0),
        (100.0,   0.0, 0.0, 0.0),
        (130.0,   0.70, 0.10, 0.10),
        (160.0,   0.90, 0.15, 0.10),
        (250.0,   0.95, 0.25, 0.15),
        (400.0,   0.80, 0.30, 0.20),
        (600.0,   0.90, 0.85, 0.72),
        (1000.0,  0.98, 0.95, 0.90),
        (3000.0,  1.00, 1.00, 1.00),
    ],
)

# Preset groups by modality for UI combo box grouping.
PRESET_GROUPS: list[tuple[str, list[TransferFunctionPreset]]] = [
    ("CT", [
        PRESET_CT_BONE,
        PRESET_CT_SOFT_TISSUE,
        PRESET_CT_LUNG,
        PRESET_CT_MUSCLE,
        PRESET_CT_ANGIO,
        PRESET_CT_FAT,
        PRESET_CT_SKIN,
        PRESET_CT_SMOOTH_ANATOMY,
        PRESET_CT_ANATOMY_COLORS,
        PRESET_CT_VIVID_ANGIO,
    ]),
    ("MR", [
        PRESET_MR_DEFAULT,
        PRESET_MR_T1_BRAIN,
        PRESET_MR_T2_BRAIN,
        PRESET_MR_MRA,
    ]),
    ("PT / NM", [
        PRESET_PT_DEFAULT,
        PRESET_NM_DEFAULT,
    ]),
    ("Generic", [
        PRESET_GENERIC_INTENSITY,
    ]),
]

BUILTIN_PRESETS: list[TransferFunctionPreset] = [
    p for _group_name, presets in PRESET_GROUPS for p in presets
]


# ---------------------------------------------------------------------------
# Transfer-function steepness (for auto sample-distance / Detail selection)
# ---------------------------------------------------------------------------

# Presets with steepness >= this threshold benefit from finer ray sampling to
# avoid wood-grain / Moiré ring artifacts (see the color/quality research doc).
# Measured peak steepness of built-ins: CT Fat ~9.1, CT Bone ~7.0,
# CT Soft Tissue ~5.0, CT Smooth Anatomy ~3.0, Generic ~2.6, MR Default ~2.0.
# 6.0 classifies the sharp-band presets (Fat, Bone, Angio) as steep while
# leaving the gentler ramps on Normal detail.
STEEP_PRESET_THRESHOLD: float = 6.0


def preset_steepness(preset: TransferFunctionPreset) -> float:
    """
    Return a scale-invariant steepness score for a preset's opacity ramp.

    Computed as ``max(|Delta opacity| * window / |Delta scalar|)`` over
    consecutive scalar-opacity control points, where ``window`` is the
    preset's natural scalar span.  Higher values mean the opacity changes
    more abruptly along the scalar axis, which aliases more strongly during
    ray casting (steep, narrow-band presets like CT Fat score high; broad
    gentle presets like CT Soft Tissue score low).

    Returns ``0.0`` for degenerate presets with fewer than two points.
    """
    pts = preset.scalar_opacity
    if len(pts) < 2:
        return 0.0
    window = max(1.0, pts[-1][0] - pts[0][0])
    max_slope = 0.0
    for (s0, o0), (s1, o1) in itertools.pairwise(pts):
        ds = abs(s1 - s0)
        if ds <= 0.0:
            continue
        max_slope = max(max_slope, abs(o1 - o0) * window / ds)
    return max_slope


def is_steep_preset(preset: TransferFunctionPreset) -> bool:
    """Return ``True`` when a preset's opacity ramp warrants finer sampling."""
    return preset_steepness(preset) >= STEEP_PRESET_THRESHOLD
