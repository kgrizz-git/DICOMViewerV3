"""
Characterization tests for ROI XLSX export helpers (Sonar S3776 slice).

Covers area unit selection and ROI-manager resolution extracted from
``roi_export_service.write_xlsx``.
"""

from __future__ import annotations

from types import SimpleNamespace

from core.roi_export_xlsx import (
    resolve_export_roi_manager,
    xlsx_area_label_value_unit,
)


def test_xlsx_area_label_value_unit_thresholds() -> None:
    assert xlsx_area_label_value_unit(150.0, 99.0) == ("Area", 1.5, "cm²")
    assert xlsx_area_label_value_unit(100.0, 99.0) == ("Area", 1.0, "cm²")
    assert xlsx_area_label_value_unit(99.9, 10.0) == ("Area", 99.9, "mm²")
    assert xlsx_area_label_value_unit(None, 12.5) == ("Area", 12.5, "pixels")


def test_resolve_export_roi_manager_prefers_sorted_first_truthy() -> None:
    mgr_a = SimpleNamespace(name="a")
    mgr_b = SimpleNamespace(name="b")
    assert resolve_export_roi_manager({}) is None
    resolved = resolve_export_roi_manager(
        {2: {"roi_manager": mgr_b}, 1: {"roi_manager": mgr_a}}
    )
    assert resolved is mgr_a


def test_resolve_export_roi_manager_all_none_returns_none() -> None:
    assert resolve_export_roi_manager({0: {"roi_manager": None}}) is None
    assert resolve_export_roi_manager({1: {}}) is None
