"""
Smoke tests for recently extracted refactor modules.

These tests focus on fast regression coverage for pure/service logic and
non-Qt delegations.
"""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from pydicom.dataset import Dataset
from pydicom.tag import Tag

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from core.dialog_action_handlers import open_about_this_file, open_export, open_overlay_config
from core.loading_pipeline import (
    batch_counts_from_merge_result,
    format_final_status,
    format_source_name,
)
from core.tag_export_analysis_service import analyze_tag_variations
from core.dicom_parser import DICOMParser
from gui.overlay_text_builder import get_corner_text, get_modality, get_overlay_text


class TestLoadingPipelineUtilitiesSmoke(unittest.TestCase):
    def test_format_source_name_single_and_multi(self):
        self.assertEqual(format_source_name(["C:/tmp/a.dcm"]), "a.dcm")
        self.assertEqual(format_source_name(["C:/tmp/a.dcm", "C:/tmp/b.dcm"]), "a.dcm...")

    def test_format_final_status_includes_skip_counts(self):
        msg = format_final_status(
            1,
            2,
            3,
            "batch",
            non_dicom_count=2,
            duplicate_count=1,
            extension_skipped_count=1,
        )
        self.assertIn("1 study, 2 series, 3 files loaded from batch", msg)
        self.assertIn("3 non-DICOM", msg)
        self.assertIn("1 duplicate", msg)

    def test_batch_counts_from_merge_result(self):
        merge_result = SimpleNamespace(
            new_series=[("study1", "series1"), ("study2", "series2")],
            appended_series=[("study1", "series3")],
            added_file_count=7,
        )
        counts = batch_counts_from_merge_result(merge_result)
        self.assertEqual(counts, (2, 3, 7))


class TestOverlayTextBuilderSmoke(unittest.TestCase):
    def test_overlay_text_modes_and_modality(self):
        ds = Dataset()
        ds.Modality = "CT"
        ds.PatientName = "John^Doe"
        parser = DICOMParser(ds)

        text = get_overlay_text(
            parser,
            mode="minimal",
            minimal_fields=["Modality", "PatientName"],
            detailed_fields=[],
            custom_fields=[],
        )
        self.assertIn("Modality: CT", text)
        self.assertIn("PatientName:", text)

        hidden = get_overlay_text(parser, "hidden", ["Modality"], [], [])
        self.assertEqual(hidden, "")
        self.assertEqual(get_modality(parser), "CT")

    def test_corner_text_privacy_and_projection(self):
        ds = Dataset()
        ds.PatientName = "Jane^Doe"
        ds.InstanceNumber = 2
        ds.SliceThickness = 1.25
        parser = DICOMParser(ds)

        text = get_corner_text(
            parser,
            tags=["PatientName", "InstanceNumber", "SliceThickness"],
            privacy_mode=True,
            total_slices=10,
            projection_enabled=True,
            projection_start_slice=1,
            projection_end_slice=3,
            projection_total_thickness=3.75,
            projection_type="mip",
        )

        self.assertIn("PatientName: PRIVACY MODE", text)
        self.assertIn("Slice 2/10 (2-4 MIP)", text)
        self.assertIn("Slice Thickness: 1.25 (3.75)", text)


class TestTagExportAnalysisSmoke(unittest.TestCase):
    def test_analyze_tag_variations_detects_constant_and_varying(self):
        patient_name_tag = str(Tag(0x0010, 0x0010))
        instance_number_tag = str(Tag(0x0020, 0x0013))

        ds1 = Dataset()
        ds1.PatientName = "Same^Name"
        ds1.InstanceNumber = 1

        ds2 = Dataset()
        ds2.PatientName = "Same^Name"
        ds2.InstanceNumber = 2

        studies = {"study1": {"series1": [ds1, ds2]}}
        selected_series = {"study1": {"series1": [0, 1]}}
        selected_tags = [patient_name_tag, instance_number_tag]

        result = analyze_tag_variations(
            studies,
            selected_series,
            selected_tags,
            include_private=False,
        )

        self.assertIn("series1", result)
        self.assertIn(patient_name_tag, result["series1"]["constant_tags"])
        self.assertIn(instance_number_tag, result["series1"]["varying_tags"])


class TestDialogActionHandlersSmoke(unittest.TestCase):
    def test_open_about_this_file_delegates_with_resolved_path(self):
        ds = Dataset()
        ds.PatientName = "Smoke^Test"
        app = SimpleNamespace(
            focused_subwindow_index=1,
            subwindow_data={
                1: {
                    "current_dataset": ds,
                    "current_study_uid": "study1",
                    "current_series_uid": "series1",
                    "current_slice_index": 5,
                }
            },
            _get_file_path_for_dataset=MagicMock(return_value="C:/tmp/a.dcm"),
            dialog_coordinator=SimpleNamespace(open_about_this_file=MagicMock()),
        )

        open_about_this_file(app)

        app._get_file_path_for_dataset.assert_called_once()
        app.dialog_coordinator.open_about_this_file.assert_called_once_with(ds, "C:/tmp/a.dcm")

    def test_open_overlay_config_passes_valid_modality_or_none(self):
        app_valid = SimpleNamespace(
            current_dataset=SimpleNamespace(Modality=" CT "),
            dialog_coordinator=SimpleNamespace(open_overlay_config=MagicMock()),
        )
        open_overlay_config(app_valid)
        app_valid.dialog_coordinator.open_overlay_config.assert_called_once_with(current_modality="CT")

        app_invalid = SimpleNamespace(
            current_dataset=SimpleNamespace(Modality="INVALID"),
            dialog_coordinator=SimpleNamespace(open_overlay_config=MagicMock()),
        )
        open_overlay_config(app_invalid)
        app_invalid.dialog_coordinator.open_overlay_config.assert_called_once_with(current_modality=None)

    def test_open_export_aggregates_subwindow_annotations(self):
        app = SimpleNamespace(
            window_level_controls=SimpleNamespace(get_window_level=lambda: (40, 400)),
            view_state_manager=SimpleNamespace(use_rescaled_values=True),
            slice_display_manager=SimpleNamespace(
                projection_enabled=True,
                projection_type="mip",
                projection_slice_count=5,
            ),
            get_focused_subwindow_index=lambda: 2,
            subwindow_managers={
                2: {
                    "roi_manager": object(),
                    "measurement_tool": object(),
                    "text_annotation_tool": object(),
                    "arrow_annotation_tool": object(),
                },
                1: {
                    "roi_manager": object(),
                    "measurement_tool": object(),
                    "text_annotation_tool": object(),
                    "arrow_annotation_tool": object(),
                },
            },
            roi_manager=object(),
            overlay_manager=object(),
            measurement_tool=object(),
            text_annotation_tool=object(),
            arrow_annotation_tool=object(),
            dialog_coordinator=SimpleNamespace(open_export=MagicMock()),
        )

        open_export(app)

        app.dialog_coordinator.open_export.assert_called_once()
        kwargs = app.dialog_coordinator.open_export.call_args.kwargs
        self.assertEqual(kwargs["current_window_center"], 40)
        self.assertEqual(kwargs["current_window_width"], 400)
        self.assertEqual(len(kwargs["subwindow_annotation_managers"]), 2)


class TestExtractedResourceFilesSmoke(unittest.TestCase):
    def test_extracted_help_and_theme_resources_exist(self):
        project_root = Path(__file__).resolve().parents[2]
        resource_paths = [
            project_root / "resources" / "themes" / "dark.qss",
            project_root / "resources" / "themes" / "light.qss",
            project_root / "resources" / "help" / "quick_start_guide.html",
            project_root / "resources" / "help" / "fusion_technical_doc.html",
        ]

        for path in resource_paths:
            self.assertTrue(path.exists(), f"Missing resource file: {path}")
            self.assertGreater(path.stat().st_size, 0, f"Empty resource file: {path}")


if __name__ == "__main__":
    unittest.main()
