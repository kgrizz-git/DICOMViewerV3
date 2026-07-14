"""
Unit tests for scan-extent tolerance helpers (no DICOM fixtures required).
"""

from __future__ import annotations

from qa.analysis_types import (
    is_physical_scan_extent_failure,
    physical_scan_extent_passes_relaxed,
)


def test_is_physical_scan_extent_failure_mri_message() -> None:
    err = (
        "ACR MRI Large analysis failed: The physical scan extent does not cover "
        "the extent of module configuration."
    )
    assert is_physical_scan_extent_failure([err])


def test_is_physical_scan_extent_failure_ct_catphan_style() -> None:
    err = (
        "ACR CT analysis failed: The physical scan extent does not match the module configuration."
    )
    assert is_physical_scan_extent_failure([err])


def test_is_physical_scan_extent_failure_negative() -> None:
    assert not is_physical_scan_extent_failure([])
    assert not is_physical_scan_extent_failure(["Unrelated error"])


def test_physical_scan_extent_passes_relaxed() -> None:
    # Strict stock would fail: max_config 101 > max_scan 100
    assert not physical_scan_extent_passes_relaxed(0.0, 100.0, 0.0, 101.0, 0.0)
    assert physical_scan_extent_passes_relaxed(0.0, 100.0, 0.0, 101.0, 1.0)
    # min boundary: config min slightly below scan min
    assert not physical_scan_extent_passes_relaxed(10.0, 200.0, 9.0, 200.0, 0.0)
    assert physical_scan_extent_passes_relaxed(10.0, 200.0, 9.0, 200.0, 1.0)
