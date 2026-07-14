"""
Tests for SubwindowLifecycleController.get_subwindow_dataset.

Ensures non-MPR panes resolve metadata from the slice list + index so HUD
(direction labels, scale, pixel readout) matches the displayed frame when
current_dataset is stale.
"""

from __future__ import annotations

import unittest

from pydicom.dataset import Dataset

from core.subwindow_lifecycle_controller import SubwindowLifecycleController


class _AppStub:
    def __init__(self, subwindow_data: dict) -> None:
        self.subwindow_data = subwindow_data


class TestGetSubwindowDataset(unittest.TestCase):
    def test_non_mpr_prefers_current_datasets_at_slice_index(self) -> None:
        d0, d1 = Dataset(), Dataset()
        d0.PatientName = "slice0"
        d1.PatientName = "slice1"
        app = _AppStub(
            {
                0: {
                    "is_mpr": False,
                    "current_datasets": [d0, d1],
                    "current_slice_index": 1,
                    "current_dataset": d0,
                }
            }
        )
        ctl = SubwindowLifecycleController(app)
        self.assertIs(ctl.get_subwindow_dataset(0), d1)

    def test_mpr_uses_current_dataset_not_slice_list(self) -> None:
        native0, native1 = Dataset(), Dataset()
        synthetic = Dataset()
        synthetic.PatientName = "mpr_overlay"
        app = _AppStub(
            {
                0: {
                    "is_mpr": True,
                    "current_datasets": [native0, native1],
                    "current_slice_index": 0,
                    "current_dataset": synthetic,
                }
            }
        )
        ctl = SubwindowLifecycleController(app)
        self.assertIs(ctl.get_subwindow_dataset(0), synthetic)

    def test_falls_back_when_index_out_of_range(self) -> None:
        lone = Dataset()
        lone.PatientName = "fallback"
        app = _AppStub(
            {
                0: {
                    "is_mpr": False,
                    "current_datasets": [lone],
                    "current_slice_index": 99,
                    "current_dataset": lone,
                }
            }
        )
        ctl = SubwindowLifecycleController(app)
        self.assertIs(ctl.get_subwindow_dataset(0), lone)

    def test_non_mpr_prefers_current_studies_series_list_when_present(self) -> None:
        """HUD must track the same dataset list as slice navigation / display_slice."""
        wrong0, wrong1 = Dataset(), Dataset()
        wrong0.PatientName = "stale_list0"
        canon0, canon1 = Dataset(), Dataset()
        canon0.PatientName = "study0"
        canon1.PatientName = "study1"
        app = _AppStub(
            {
                0: {
                    "is_mpr": False,
                    "current_study_uid": "1.2.3",
                    "current_series_uid": "SERIES",
                    "current_datasets": [wrong0, wrong1],
                    "current_slice_index": 1,
                    "current_dataset": wrong0,
                }
            }
        )
        app.current_studies = {"1.2.3": {"SERIES": [canon0, canon1]}}
        ctl = SubwindowLifecycleController(app)
        self.assertIs(ctl.get_subwindow_dataset(0), canon1)


if __name__ == "__main__":
    unittest.main()
