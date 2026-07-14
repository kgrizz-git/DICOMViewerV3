"""Qt-free unit tests for core.mpr_view_math (refactor Stream D).

Deterministic checks for the pure MPR view/display helpers extracted from
gui/mpr_controller.py. (The reslice math itself already lives in
core/mpr_builder.py / core/mpr_volume.py and is covered elsewhere.)
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.mpr_view_math import (
    array_to_pil,
    auto_window_level,
    build_mpr_banner_text,
    compute_mpr_combine_range,
)

# --- compute_mpr_combine_range ---------------------------------------------

def test_combine_range_center_and_edges():
    assert compute_mpr_combine_range(8, 4, 4) == (2, 5)  # centered
    assert compute_mpr_combine_range(8, 0, 4) == (0, 3)  # clamp low
    assert compute_mpr_combine_range(8, 7, 4) == (4, 7)  # clamp high


def test_combine_range_empty_and_clamps():
    assert compute_mpr_combine_range(0, 5, 4) == (0, 0)
    assert compute_mpr_combine_range(-3, 5, 4) == (0, 0)
    # n_planes wider than stack -> whole stack
    assert compute_mpr_combine_range(3, 1, 10) == (0, 2)
    # n_planes < 1 coerced to 1
    assert compute_mpr_combine_range(5, 2, 0) == (2, 2)


# --- build_mpr_banner_text --------------------------------------------------

def test_banner_includes_active_combine_mode():
    assert build_mpr_banner_text({"mpr_orientation": "Axial", "mpr_combine_enabled": True, "mpr_combine_mode": "aip"}) == "MPR - Axial (AIP)"
    assert build_mpr_banner_text({"mpr_orientation": "Axial", "mpr_combine_enabled": True, "mpr_combine_mode": "mip"}) == "MPR - Axial (MIP)"
    assert build_mpr_banner_text({"mpr_orientation": "Axial", "mpr_combine_enabled": True, "mpr_combine_mode": "minip"}) == "MPR - Axial (MinIP)"


def test_banner_without_combine_and_defaults():
    assert build_mpr_banner_text({"mpr_orientation": "Axial"}) == "MPR - Axial"
    assert build_mpr_banner_text({}) == "MPR - MPR"  # missing orientation -> default
    # unknown mode falls back to uppercased value
    assert build_mpr_banner_text({"mpr_orientation": "Cor", "mpr_combine_enabled": True, "mpr_combine_mode": "avg"}) == "MPR - Cor (AVG)"


# --- auto_window_level ------------------------------------------------------

def test_auto_window_level_known_array():
    arr = np.arange(0, 101, dtype=np.float32)  # 0..100
    wc, ww = auto_window_level(arr)
    # 2nd/98th percentile of 0..100 are 2 and 98 -> wc=50, ww=96
    assert wc == 50.0
    assert ww == 96.0


def test_auto_window_level_empty_and_nonfinite():
    assert auto_window_level(np.array([], dtype=np.float32)) == (0.0, 1.0)
    assert auto_window_level(np.full(5, np.nan, dtype=np.float32)) == (0.0, 1.0)


def test_auto_window_level_floors_width_at_one():
    wc, ww = auto_window_level(np.full(10, 7.0, dtype=np.float32))  # constant
    assert ww == 1.0
    assert wc == 7.0


# --- array_to_pil -----------------------------------------------------------

def test_array_to_pil_linear_mapping():
    arr = np.array([[0.0, 255.0]], dtype=np.float32)
    img = array_to_pil(arr, window_center=127.5, window_width=255.0)
    assert img is not None
    assert img.mode == "L"
    assert img.size == (2, 1)  # PIL size is (width, height)
    px = np.asarray(img)
    assert px[0, 0] == 0
    assert px[0, 1] == 255


def test_array_to_pil_clips_out_of_window():
    arr = np.array([[-100.0, 1000.0]], dtype=np.float32)
    px = np.asarray(array_to_pil(arr, window_center=127.5, window_width=255.0))
    assert px[0, 0] == 0      # below window -> clipped to 0
    assert px[0, 1] == 255    # above window -> clipped to 255
