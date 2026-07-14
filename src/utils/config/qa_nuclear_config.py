"""
Default constants and bounds for pylinac.nuclear QA workflows.

Mirrors utils.config.qa_pylinac_config (ACR) but for nuclear-medicine QC.
Only the first shipped class (PlanarUniformity) is covered here; add new
class defaults alongside these as further nuclear tests are integrated.

The values match pylinac 3.43.x ``analyze(...)`` defaults so that a run left
untouched is stock-pylinac equivalent (see each NuclearOptions subclass's
``is_pylinac_default`` in qa.analysis_types).
"""

from __future__ import annotations

# analysis_type discriminators routed by qa.worker / qa.pylinac_nuclear.
NUCLEAR_PLANAR_UNIFORMITY: str = "nuclear_planar_uniformity"
NUCLEAR_FOUR_BAR_RESOLUTION: str = "nuclear_four_bar_resolution"
NUCLEAR_QUADRANT_RESOLUTION: str = "nuclear_quadrant_resolution"
NUCLEAR_CENTER_OF_ROTATION: str = "nuclear_center_of_rotation"
NUCLEAR_TOMOGRAPHIC_RESOLUTION: str = "nuclear_tomographic_resolution"
NUCLEAR_MAX_COUNT_RATE: str = "nuclear_max_count_rate"
NUCLEAR_TOMOGRAPHIC_UNIFORMITY: str = "nuclear_tomographic_uniformity"
NUCLEAR_TOMOGRAPHIC_CONTRAST: str = "nuclear_tomographic_contrast"
NUCLEAR_SIMPLE_SENSITIVITY: str = "nuclear_simple_sensitivity"

# pylinac.nuclear class names recorded in provenance.
PLANAR_UNIFORMITY_CLASS: str = "PlanarUniformity"
FOUR_BAR_RESOLUTION_CLASS: str = "FourBarResolution"
QUADRANT_RESOLUTION_CLASS: str = "QuadrantResolution"
CENTER_OF_ROTATION_CLASS: str = "CenterOfRotation"
TOMOGRAPHIC_RESOLUTION_CLASS: str = "TomographicResolution"
MAX_COUNT_RATE_CLASS: str = "MaxCountRate"
TOMOGRAPHIC_UNIFORMITY_CLASS: str = "TomographicUniformity"
TOMOGRAPHIC_CONTRAST_CLASS: str = "TomographicContrast"
SIMPLE_SENSITIVITY_CLASS: str = "SimpleSensitivity"

# PlanarUniformity.analyze(...) defaults (pylinac 3.43.2).
DEFAULT_UFOV_RATIO: float = 0.95
DEFAULT_CFOV_RATIO: float = 0.75
DEFAULT_WINDOW_SIZE: int = 5
DEFAULT_THRESHOLD: float = 0.75

# Viewer-side guardrails (not upstream pylinac limits). UFOV/CFOV are fractions
# of the field of view; window_size is an odd pixel count for differential
# uniformity smoothing; threshold is a fraction of the mean.
MIN_FOV_RATIO: float = 0.05
MAX_FOV_RATIO: float = 1.0
MIN_WINDOW_SIZE: int = 1
MAX_WINDOW_SIZE: int = 99
MIN_THRESHOLD: float = 0.0
MAX_THRESHOLD: float = 1.0

# FourBarResolution.analyze(...) defaults (pylinac 3.43.2). separation_mm is the
# known bar separation of the phantom; roi_width_mm is the profile ROI width.
DEFAULT_SEPARATION_MM: float = 100.0
DEFAULT_ROI_WIDTH_MM: float = 10.0

# Viewer-side guardrails (not upstream pylinac limits).
MIN_SEPARATION_MM: float = 1.0
MAX_SEPARATION_MM: float = 1000.0
MIN_ROI_WIDTH_MM: float = 1.0
MAX_ROI_WIDTH_MM: float = 200.0

# QuadrantResolution.analyze(...): bar_widths is REQUIRED by pylinac (exactly 4,
# one per quadrant) and is phantom-specific — these are editable starting values
# matching the common four-quadrant bar phantom, not a pylinac default.
# roi_diameter_mm / distance_from_center_mm match the pylinac analyze() defaults.
DEFAULT_BAR_WIDTHS_MM: tuple[float, float, float, float] = (4.23, 3.18, 2.54, 2.12)
DEFAULT_ROI_DIAMETER_MM: float = 70.0
DEFAULT_DISTANCE_FROM_CENTER_MM: float = 130.0
QUADRANT_BAR_COUNT: int = 4

# Viewer-side guardrails (not upstream pylinac limits).
MIN_BAR_WIDTH_MM: float = 0.1
MAX_BAR_WIDTH_MM: float = 100.0
MIN_ROI_DIAMETER_MM: float = 1.0
MAX_ROI_DIAMETER_MM: float = 500.0
MIN_DISTANCE_FROM_CENTER_MM: float = 0.0
MAX_DISTANCE_FROM_CENTER_MM: float = 1000.0

# MaxCountRate.analyze(frame_duration=1.0) — seconds per dynamic frame.
DEFAULT_FRAME_DURATION_S: float = 1.0
MIN_FRAME_DURATION_S: float = 0.001
MAX_FRAME_DURATION_S: float = 3600.0
# CenterOfRotation and TomographicResolution take no analyze() parameters.

# TomographicUniformity.analyze(...) defaults (pylinac 3.43.2). first/last_frame
# select the slice range to collapse (last_frame=-1 means "to the end").
DEFAULT_TU_FIRST_FRAME: int = 0
DEFAULT_TU_LAST_FRAME: int = -1
DEFAULT_TU_UFOV_RATIO: float = 0.8
DEFAULT_TU_CFOV_RATIO: float = 0.75
DEFAULT_CENTER_RATIO: float = 0.4
DEFAULT_TU_THRESHOLD: float = 0.75
DEFAULT_TU_WINDOW_SIZE: int = 5
# Frame indices: -1 is a sentinel for "last frame".
MIN_FRAME_INDEX: int = -1
MAX_FRAME_INDEX: int = 100000

# TomographicContrast.analyze(...) defaults (pylinac 3.43.2). The sphere
# geometry has pylinac defaults (unlike QuadrantResolution's bar widths).
DEFAULT_SPHERE_DIAMETERS_MM: tuple[float, ...] = (38.0, 31.8, 25.4, 19.1, 15.9, 12.7)
DEFAULT_SPHERE_ANGLES: tuple[float, ...] = (-10.0, -70.0, -130.0, -190.0, 110.0, 50.0)
DEFAULT_TC_UFOV_RATIO: float = 0.8
DEFAULT_SEARCH_WINDOW_PX: int = 5
DEFAULT_SEARCH_SLICES: int = 3
SPHERE_COUNT: int = 6
# Viewer-side guardrails (not upstream pylinac limits).
MIN_SPHERE_DIAMETER_MM: float = 0.1
MAX_SPHERE_DIAMETER_MM: float = 500.0
MIN_SPHERE_ANGLE_DEG: float = -360.0
MAX_SPHERE_ANGLE_DEG: float = 360.0
MIN_SEARCH_WINDOW_PX: int = 1
MAX_SEARCH_WINDOW_PX: int = 99
MIN_SEARCH_SLICES: int = 1
MAX_SEARCH_SLICES: int = 99

# SimpleSensitivity.analyze(activity_mbq, nuclide) — both required, no pylinac
# defaults. nuclide is a string name mapped to pylinac's Nuclide enum in the
# runner (the dialog must not import pylinac). NUCLIDE_NAMES mirrors the enum.
NUCLIDE_NAMES: tuple[str, ...] = ("Tc99m", "Ga67", "I131", "In111", "Lu177", "Y90")
DEFAULT_NUCLIDE: str = "Tc99m"
DEFAULT_ACTIVITY_MBQ: float = 0.0  # 0 forces the user to enter a real value
MIN_ACTIVITY_MBQ: float = 0.0
MAX_ACTIVITY_MBQ: float = 1_000_000.0
