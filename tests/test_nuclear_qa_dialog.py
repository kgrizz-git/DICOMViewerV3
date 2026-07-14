"""
Qt tests for the nuclear QC options dialog (plan T12).

Uses the session ``qapp`` fixture from conftest. Exercises default values, the
mapping to the per-class NuclearOptions, and that custom values round-trip to
analyze kwargs.
"""

from __future__ import annotations

import pytest

from gui.dialogs.nuclear_qa_dialog import NuclearQaOptionsDialog
from utils.config.qa_nuclear_config import (
    CENTER_OF_ROTATION_CLASS,
    DEFAULT_CFOV_RATIO,
    DEFAULT_ROI_WIDTH_MM,
    DEFAULT_SEPARATION_MM,
    DEFAULT_THRESHOLD,
    DEFAULT_UFOV_RATIO,
    DEFAULT_WINDOW_SIZE,
    FOUR_BAR_RESOLUTION_CLASS,
    MAX_COUNT_RATE_CLASS,
    PLANAR_UNIFORMITY_CLASS,
    QUADRANT_RESOLUTION_CLASS,
    SIMPLE_SENSITIVITY_CLASS,
    TOMOGRAPHIC_CONTRAST_CLASS,
    TOMOGRAPHIC_RESOLUTION_CLASS,
    TOMOGRAPHIC_UNIFORMITY_CLASS,
)

pytestmark = pytest.mark.qt


def test_dialog_defaults_match_pylinac(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    opts = dlg.get_options()
    assert opts.analysis_class == PLANAR_UNIFORMITY_CLASS
    assert opts.ufov_ratio == DEFAULT_UFOV_RATIO
    assert opts.cfov_ratio == DEFAULT_CFOV_RATIO
    assert opts.window_size == DEFAULT_WINDOW_SIZE
    assert opts.threshold == DEFAULT_THRESHOLD
    # Default selection is stock-pylinac equivalent.
    assert opts.is_pylinac_default() is True
    dlg.deleteLater()


def test_dialog_custom_values_roundtrip(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    dlg._ufov.setValue(0.90)
    dlg._cfov.setValue(0.70)
    dlg._window.setValue(7)
    dlg._threshold.setValue(0.60)
    opts = dlg.get_options()
    assert opts.analyze_kwargs() == {
        "ufov_ratio": 0.90,
        "cfov_ratio": 0.70,
        "window_size": 7,
        "threshold": 0.60,
    }
    # Non-default parameters are flagged as not stock-equivalent.
    assert opts.is_pylinac_default() is False
    dlg.deleteLater()


def test_dialog_supported_tests_offered(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    classes = [dlg._test.itemData(i) for i in range(dlg._test.count())]
    assert classes == [
        PLANAR_UNIFORMITY_CLASS,
        FOUR_BAR_RESOLUTION_CLASS,
        QUADRANT_RESOLUTION_CLASS,
        CENTER_OF_ROTATION_CLASS,
        TOMOGRAPHIC_RESOLUTION_CLASS,
        MAX_COUNT_RATE_CLASS,
        TOMOGRAPHIC_UNIFORMITY_CLASS,
        TOMOGRAPHIC_CONTRAST_CLASS,
        SIMPLE_SENSITIVITY_CLASS,
    ]
    dlg.deleteLater()


def test_dialog_simple_sensitivity_options(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    # Simple Sensitivity is the last entry (index 8).
    dlg._test.setCurrentIndex(8)
    assert dlg._stack.currentIndex() == 8
    dlg._activity.setValue(12.5)
    dlg._nuclide.setCurrentText("Ga67")
    opts = dlg.get_options()
    assert opts.analysis_class == SIMPLE_SENSITIVITY_CLASS
    assert opts.activity_mbq == 12.5
    assert opts.nuclide == "Ga67"
    assert opts.background_path is None  # not chosen
    assert opts.is_pylinac_default() is False
    dlg.deleteLater()


def test_dialog_tier2_options(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    # Tomographic Uniformity (index 6).
    dlg._test.setCurrentIndex(6)
    assert dlg._stack.currentIndex() == 6
    tu = dlg.get_options()
    assert tu.analysis_class == TOMOGRAPHIC_UNIFORMITY_CLASS
    assert set(tu.analyze_kwargs()) == {
        "first_frame", "last_frame", "ufov_ratio", "cfov_ratio",
        "center_ratio", "threshold", "window_size",
    }
    assert tu.is_pylinac_default() is True
    # Tomographic Contrast (index 7) — 6 sphere diameter/angle spinboxes.
    dlg._test.setCurrentIndex(7)
    assert dlg._stack.currentIndex() == 7
    assert len(dlg._sphere_diameters) == 6 and len(dlg._sphere_angles) == 6
    dlg._sphere_diameters[0].setValue(40.0)
    tc = dlg.get_options()
    assert tc.analysis_class == TOMOGRAPHIC_CONTRAST_CLASS
    assert tc.analyze_kwargs()["sphere_diameters_mm"][0] == 40.0
    assert tc.is_pylinac_default() is False
    dlg.deleteLater()


def test_dialog_tier1_options(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    # Center of Rotation (index 3) and Tomographic Resolution (index 4): no params.
    dlg._test.setCurrentIndex(3)
    assert dlg.get_options().analysis_class == CENTER_OF_ROTATION_CLASS
    assert dlg.get_options().analyze_kwargs() == {}
    dlg._test.setCurrentIndex(4)
    assert dlg.get_options().analysis_class == TOMOGRAPHIC_RESOLUTION_CLASS
    # Max Count Rate (index 5): frame_duration.
    dlg._test.setCurrentIndex(5)
    assert dlg._stack.currentIndex() == 5
    dlg._frame_duration.setValue(2.0)
    opts = dlg.get_options()
    assert opts.analysis_class == MAX_COUNT_RATE_CLASS
    assert opts.analyze_kwargs() == {"frame_duration": 2.0}
    assert opts.is_pylinac_default() is False
    dlg.deleteLater()


def test_dialog_switches_params_and_class_for_four_bar(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    # Select Four Bar Resolution (index 1); the parameter stack follows.
    dlg._test.setCurrentIndex(1)
    assert dlg._stack.currentIndex() == 1
    dlg._separation.setValue(50.0)
    dlg._roi_width.setValue(8.0)
    opts = dlg.get_options()
    assert opts.analysis_class == FOUR_BAR_RESOLUTION_CLASS
    assert opts.analyze_kwargs() == {"separation_mm": 50.0, "roi_width_mm": 8.0}
    assert opts.is_pylinac_default() is False


def test_dialog_four_bar_defaults(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    dlg._test.setCurrentIndex(1)
    opts = dlg.get_options()
    assert opts.separation_mm == DEFAULT_SEPARATION_MM
    assert opts.roi_width_mm == DEFAULT_ROI_WIDTH_MM
    assert opts.is_pylinac_default() is True
    dlg.deleteLater()


def test_dialog_quadrant_page_and_options(qapp) -> None:
    dlg = NuclearQaOptionsDialog()
    # Quadrant Resolution is index 2; the parameter stack follows.
    dlg._test.setCurrentIndex(2)
    assert dlg._stack.currentIndex() == 2
    # Four bar-width spinboxes are present (one per quadrant).
    assert len(dlg._bar_widths) == 4
    dlg._bar_widths[0].setValue(5.0)
    dlg._roi_diameter.setValue(60.0)
    opts = dlg.get_options()
    assert opts.analysis_class == QUADRANT_RESOLUTION_CLASS
    kwargs = opts.analyze_kwargs()
    assert kwargs["bar_widths"][0] == 5.0
    assert len(kwargs["bar_widths"]) == 4
    assert kwargs["roi_diameter_mm"] == 60.0
    # ROI geometry changed from default -> not stock-equivalent.
    assert opts.is_pylinac_default() is False
    dlg.deleteLater()
